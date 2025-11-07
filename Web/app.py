'''
   Copyright 2025 Maximilian Gründinger

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''
"""
Inventarsystem - Flask Web Application

This application provides an inventory management system with user authentication,
item tracking, QR code generation, and borrowing/returning functionality.

The system uses MongoDB for data storage and provides separate interfaces for
regular users and administrators.

Features:
- User authentication (login/logout)
- Item management (add, delete, view)
- Borrowing and returning items
- QR code generation for items
- Administrative functions
- History logging of item usage
- Booking and reservation of items
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, get_flashed_messages, jsonify, Response
from werkzeug.utils import secure_filename
import user as us
import items as it
import ausleihung as au
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from bson.objectid import ObjectId
from urllib.parse import urlparse, urlunparse
import requests
import os
import json
import datetime
import time
import traceback
import re
import io
# QR Code functionality deactivated
# import qrcode
# from qrcode.constants import ERROR_CORRECT_L
import threading
import sys
import shutil
import uuid
from PIL import Image, ImageOps
import mimetypes
import subprocess

# Set base directory and centralized settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import settings as cfg


app = Flask(__name__, static_folder='static')  # Correctly set static folder
app.secret_key = cfg.SECRET_KEY
app.debug = cfg.DEBUG
app.config['UPLOAD_FOLDER'] = cfg.UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = cfg.THUMBNAIL_FOLDER
app.config['PREVIEW_FOLDER'] = cfg.PREVIEW_FOLDER
app.config['ALLOWED_EXTENSIONS'] = set(cfg.ALLOWED_EXTENSIONS)
# app.config['QR_CODE_FOLDER'] = cfg.QR_CODE_FOLDER  # QR Code storage deactivated

# Thumbnail sizes
THUMBNAIL_SIZE = cfg.THUMBNAIL_SIZE
PREVIEW_SIZE = cfg.PREVIEW_SIZE

__version__ = cfg.APP_VERSION
Host = cfg.HOST
Port = cfg.PORT

MONGODB_HOST = cfg.MONGODB_HOST
MONGODB_PORT = cfg.MONGODB_PORT
MONGODB_DB = cfg.MONGODB_DB
SCHEDULER_INTERVAL = cfg.SCHEDULER_INTERVAL_MIN
SSL_CERT = cfg.SSL_CERT
SSL_KEY = cfg.SSL_KEY


SCHOOL_PERIODS = cfg.SCHOOL_PERIODS

# Apply the configuration for general use throughout the app
APP_VERSION = __version__

@app.context_processor
def inject_version():
    """Inject global template variables."""
    return {'APP_VERSION': APP_VERSION, 'school_periods': SCHOOL_PERIODS}

# Create necessary directories at startup
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['THUMBNAIL_FOLDER']):
    os.makedirs(app.config['THUMBNAIL_FOLDER'])
if not os.path.exists(app.config['PREVIEW_FOLDER']):
    os.makedirs(app.config['PREVIEW_FOLDER'])
# QR Code directory creation deactivated
# if not os.path.exists(app.config['QR_CODE_FOLDER']):
#     os.makedirs(app.config['QR_CODE_FOLDER'])

# Create backup directories
BACKUP_FOLDER = cfg.BACKUP_FOLDER
if not os.path.exists(BACKUP_FOLDER):
    try:
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
    except PermissionError:
        # Fallback: use a backup directory inside the application directory (writable)
        fallback_backup = os.path.join(BASE_DIR, 'backups')
        try:
            os.makedirs(fallback_backup, exist_ok=True)
            BACKUP_FOLDER = fallback_backup
            print(f"Warnung: Konnte BACKUP_FOLDER nicht erstellen. Fallback genutzt: {BACKUP_FOLDER}")
        except Exception as e:
            print(f"Fehler: Backup-Verzeichnis konnte nicht erstellt werden: {e}")

def create_daily_backup():
    """
    Erstellt täglich ein Backup der Ausleihungsdatenbank
    """
    try:
        print(f"[{datetime.datetime.now()}] Erstelle Backup der Ausleihungsdatenbank...")
        result = au.create_backup_database()
        if result:
            print(f"[{datetime.datetime.now()}] Backup erfolgreich erstellt")
        else:
            print(f"[{datetime.datetime.now()}] Fehler beim Erstellen des Backups")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Ausnahme beim Erstellen des Backups: {str(e)}")

def update_appointment_statuses():
    """
    Aktualisiert automatisch die Status aller Terminplaner-Einträge.
    Diese Funktion wird jede Minute ausgeführt und überprüft:
    - Geplante Termine, die aktiviert werden sollten
    - Aktive Termine, die beendet werden sollten
    """
    current_time = datetime.datetime.now()
    # Prepare logging early so it's available in exception paths
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, 'scheduler.log')

    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{current_time}] Starte automatische Statusaktualisierung...\n")

        print(f"[{current_time}] Starte automatische Statusaktualisierung...")

        # Hole alle Termine mit Status 'planned' oder 'active'
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        ausleihungen = db['ausleihungen']

        # Finde alle Termine, die status updates benötigen
        appointments_to_check = list(ausleihungen.find({
            'Status': {'$in': ['planned', 'active']}
        }))

        updated_count = 0
        activated_count = 0
        completed_count = 0

        for appointment in appointments_to_check:
            old_status = appointment.get('Status')

            # Aktuellen Status bestimmen
            new_status = au.get_current_status(appointment, log_changes=True, user='scheduler')

            # Wenn sich der Status geändert hat, aktualisiere in der Datenbank
            if new_status != old_status:
                result = ausleihungen.update_one(
                    {'_id': appointment['_id']},
                    {'$set': {
                        'Status': new_status,
                        'LastUpdated': current_time
                    }}
                )

                if result.modified_count > 0:
                    updated_count += 1
                    if new_status == 'active':
                        activated_count += 1
                    elif new_status == 'completed':
                        completed_count += 1

                    log_msg = f"  - Termin {appointment['_id']}: {old_status} → {new_status}"
                    print(log_msg)
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{current_time}] {log_msg}\n")

        client.close()

        if updated_count > 0:
            result_msg = f"Statusaktualisierung abgeschlossen: {updated_count} Termine aktualisiert"
            detail_msg = f"  - {activated_count} aktiviert, {completed_count} abgeschlossen"
            print(f"[{current_time}] {result_msg}")
            print(f"[{current_time}] {detail_msg}")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{current_time}] {result_msg}\n")
                f.write(f"[{current_time}] {detail_msg}\n")
        else:
            result_msg = "Statusaktualisierung abgeschlossen: Keine Änderungen erforderlich"
            print(f"[{current_time}] {result_msg}")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{current_time}] {result_msg}\n")

    except Exception as e:
        error_msg = f"Fehler bei der automatischen Statusaktualisierung: {str(e)}"
        print(f"[{datetime.datetime.now()}] {error_msg}")
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.datetime.now()}] {error_msg}\n")
        except Exception:
            pass
        import traceback
        traceback.print_exc()

# Schedule jobs
scheduler = BackgroundScheduler()
if cfg.SCHEDULER_ENABLED:
    scheduler.add_job(func=create_daily_backup, trigger="interval", hours=cfg.BACKUP_INTERVAL_HOURS)
    scheduler.add_job(func=update_appointment_statuses, trigger="interval", minutes=cfg.SCHEDULER_INTERVAL_MIN)
    scheduler.start()

# Register shutdown handler to stop scheduler when app is terminated
import atexit
atexit.register(lambda: scheduler.shutdown() if cfg.SCHEDULER_ENABLED else None)

def allowed_file(filename, file_content=None, max_size_mb=cfg.MAX_UPLOAD_MB):
    """
    Check if a file has an allowed extension and valid content.
    
    Args:
        filename (str): Name of the file to check
        file_content (FileStorage, optional): The actual file object to validate content
        max_size_mb (int, optional): Maximum allowed file size in MB
        
    Returns:
        tuple: (bool, str) - True if the file is valid, False otherwise
               along with an error message if not valid
    """
    # Check file extension
    if '.' not in filename:
        return False, f"Datei '{filename}' hat keine Dateiendung. Erlaubte Formate: {', '.join(app.config['ALLOWED_EXTENSIONS'])}"
    
    extension = filename.rsplit('.', 1)[1].lower()
    allowed_extensions_lower = {ext.lower() for ext in app.config['ALLOWED_EXTENSIONS']}
    if extension not in allowed_extensions_lower:
        app.logger.warning(f"File extension not allowed: {extension} for file {filename}. Allowed: {allowed_extensions_lower}")
        return False, f"Datei '{filename}' hat ein nicht unterstütztes Format ({extension}). Erlaubte Formate: {', '.join(app.config['ALLOWED_EXTENSIONS'])}"
    
    # Check file size if content is provided
    if file_content is not None:
        # Check file size
        file_content.seek(0, os.SEEK_END)
        file_size = file_content.tell() / (1024 * 1024)  # Size in MB
        file_content.seek(0)  # Reset file pointer to beginning
        
        if file_size > max_size_mb:
            return False, f"Datei '{filename}' ist zu groß ({file_size:.1f} MB). Maximale Größe: {max_size_mb} MB."
        
        # Verify file content matches extension
        try:
            if extension in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                try:
                    # Special debug for PNG files
                    if extension == 'png':
                        app.logger.info(f"PNG DEBUG: Validating PNG file: {filename}, size: {file_size:.2f}MB")
                        # Save first few bytes for magic number checking
                        header_bytes = file_content.read(32)  # Reading more bytes for deeper analysis
                        file_content.seek(0)  # Reset pointer
                        
                        # Check PNG magic number (first 8 bytes)
                        png_signature = b'\x89PNG\r\n\x1a\n'
                        is_valid_signature = header_bytes.startswith(png_signature)
                        
                        # Create a hex dump of the header for debugging
                        hex_dump = ' '.join([f"{b:02x}" for b in header_bytes[:16]])
                        app.logger.info(f"PNG DEBUG: File {filename} - Header hex dump: {hex_dump}")
                        app.logger.info(f"PNG DEBUG: Valid PNG signature: {is_valid_signature}, first bytes: {header_bytes[:8]!r}")
                        
                        # More detailed analysis of PNG chunks
                        if is_valid_signature:
                            try:
                                # IHDR chunk should start at byte 8
                                if header_bytes[8:12] == b'IHDR':
                                    app.logger.info(f"PNG DEBUG: Found IHDR chunk at correct position")
                                else:
                                    app.logger.warning(f"PNG DEBUG: IHDR chunk not found at expected position. Found: {header_bytes[8:12]!r}")
                            except Exception as chunk_err:
                                app.logger.error(f"PNG DEBUG: Error analyzing PNG chunks: {str(chunk_err)}")
                        else:
                            app.logger.error(f"PNG DEBUG: Invalid PNG signature for {filename}. Expected: {png_signature!r}")
                    
                    with Image.open(file_content) as img:
                        # Verify it's a valid image by accessing its format and size
                        img_format = img.format
                        img_mode = img.mode
                        img_size = img.size
                        
                        if extension == 'png':
                            app.logger.info(f"PNG DEBUG: Successfully opened PNG - Format: {img_format}, Mode: {img_mode}, Size: {img_size[0]}x{img_size[1]}")
                            # Add more PNG-specific checks
                            app.logger.info(f"PNG DEBUG: Image info - Bands: {len(img.getbands())}, Bands: {img.getbands()}")
                            # Check if there's transparency
                            has_alpha = 'A' in img.getbands() or img.mode == 'P' and img.info.get('transparency') is not None
                            app.logger.info(f"PNG DEBUG: Has transparency: {has_alpha}")
                        
                        if not img_format:
                            if extension == 'png':
                                app.logger.error(f"PNG DEBUG: Invalid format - got None for {filename}")
                            return False, f"Datei '{filename}' scheint keine gültige Bilddatei zu sein."
                        
                        file_content.seek(0)  # Reset file pointer after reading
                except Exception as e:
                    error_msg = f"Error validating image content for {filename}: {str(e)}"
                    app.logger.error(error_msg)
                    
                    if extension == 'png':
                        app.logger.error(f"PNG DEBUG: Failed to process PNG file: {filename}")
                        app.logger.error(f"PNG DEBUG: Error details: {str(e)}")
                        app.logger.error(f"PNG DEBUG: Error type: {type(e).__name__}")
                        
                        # Get the full traceback as string and log it
                        import io
                        tb_output = io.StringIO()
                        traceback.print_exc(file=tb_output)
                        app.logger.error(f"PNG DEBUG: Full traceback for {filename}:\n{tb_output.getvalue()}")
                        
                        # Try to manually read the file data and check it
                        try:
                            file_content.seek(0)
                            file_bytes = file_content.read(1024)  # Read first KB
                            file_content.seek(0)  # Reset again
                            
                            hex_signature = ' '.join([f"{b:02x}" for b in file_bytes[:16]])
                            app.logger.error(f"PNG DEBUG: Raw file bytes (first 16): {hex_signature}")
                            
                            # Check for common corruption patterns
                            if not file_bytes.startswith(png_signature):
                                app.logger.error(f"PNG DEBUG: File doesn't start with PNG signature")
                                if file_bytes.startswith(b'<'):
                                    app.logger.error(f"PNG DEBUG: File appears to be XML/HTML, not PNG")
                                elif file_bytes.startswith(b'\xff\xd8'):
                                    app.logger.error(f"PNG DEBUG: File appears to be JPEG, not PNG")
                            
                            # Check file size again to make sure it's not empty
                            file_content.seek(0, os.SEEK_END)
                            actual_size = file_content.tell()
                            file_content.seek(0)
                            if actual_size < 100:  # Very small for a PNG
                                app.logger.error(f"PNG DEBUG: File is suspiciously small: {actual_size} bytes")
                        except Exception as raw_err:
                            app.logger.error(f"PNG DEBUG: Error during raw file analysis: {str(raw_err)}")
                        
                        traceback.print_exc()
                    
                    return False, f"Datei '{filename}' konnte nicht als Bild erkannt werden. Fehler: {str(e)}"
                    
            # Add more content type validations as needed for other file types
                
        except Exception as e:
            app.logger.error(f"Error during content validation for {filename}: {str(e)}")
            file_content.seek(0)  # Reset file pointer in case of error
            # Don't reject the file based on content validation failure alone
    
    return True, ""


def strip_whitespace(value):
    """
    Strip leading and trailing whitespace from a string or from each item in a list.
    
    Args:
        value: String or list of strings to strip
        
    Returns:
        String or list of strings with whitespace stripped
    """
    if isinstance(value, str):
        return value.strip()
    elif isinstance(value, list):
        return [item.strip() if isinstance(item, str) else item for item in value]
    return value


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Serve uploaded files from the uploads directory.
    
    Args:
        filename (str): Name of the file to serve
        
    Returns:
        flask.Response: The requested file or placeholder image if not found
    """
    try:
        # Check production path first (deployed environment)
        prod_path = "/opt/Inventarsystem/Web/uploads"
        dev_path = app.config['UPLOAD_FOLDER']
        if os.path.exists(os.path.join(prod_path, filename)):
            return send_from_directory(prod_path, filename)
        # Then check development path
        if os.path.exists(os.path.join(dev_path, filename)):
            return send_from_directory(dev_path, filename)
            
        # Use a placeholder image if file not found - first try SVG, then PNG
        svg_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
        png_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
        
        if os.path.exists(svg_placeholder_path):
            return send_from_directory(app.static_folder, 'img/no-image.svg')
        elif os.path.exists(png_placeholder_path):
            return send_from_directory(app.static_folder, 'img/no-image.png')
        
        # Default placeholder from static folder
        return send_from_directory(app.static_folder, 'favicon.ico')
    except Exception as e:
        print(f"Error serving file {filename}: {str(e)}")
        return Response("Image not found", status=404)


@app.route('/thumbnails/<filename>')
def thumbnail_file(filename):
    """
    Serve thumbnail files from the thumbnails directory.
    
    Args:
        filename (str): Name of the thumbnail file to serve
        
    Returns:
        flask.Response: The requested thumbnail file or placeholder image if not found
    """
    try:
        # Check production path first
        prod_path = "/var/Inventarsystem/Web/thumbnails"
        dev_path = app.config['THUMBNAIL_FOLDER']
        if os.path.exists(os.path.join(prod_path, filename)):
            return send_from_directory(prod_path, filename)
        if os.path.exists(os.path.join(dev_path, filename)):
            return send_from_directory(dev_path, filename)
            
        # Use a placeholder image if file not found - first try SVG, then PNG
        svg_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
        png_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
        
        if os.path.exists(svg_placeholder_path):
            return send_from_directory(app.static_folder, 'img/no-image.svg')
        elif os.path.exists(png_placeholder_path):
            return send_from_directory(app.static_folder, 'img/no-image.png')
        else:
            return send_from_directory(app.static_folder, 'favicon.ico')
    except Exception as e:
        print(f"Error serving thumbnail {filename}: {str(e)}")
        return Response("Thumbnail not found", status=404)


@app.route('/previews/<filename>')
def preview_file(filename):
    """
    Serve preview files from the previews directory.
    
    Args:
        filename (str): Name of the preview file to serve
        
    Returns:
        flask.Response: The requested preview file or placeholder image if not found
    """
    try:
        # Check production path first
        prod_path = "/var/Inventarsystem/Web/previews"
        dev_path = app.config['PREVIEW_FOLDER']
        if os.path.exists(os.path.join(prod_path, filename)):
            return send_from_directory(prod_path, filename)
        if os.path.exists(os.path.join(dev_path, filename)):
            return send_from_directory(dev_path, filename)
            
        # Use a placeholder image if file not found - first try SVG, then PNG
        svg_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
        png_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
        
        if os.path.exists(svg_placeholder_path):
            return send_from_directory(app.static_folder, 'img/no-image.svg')
        elif os.path.exists(png_placeholder_path):
            return send_from_directory(app.static_folder, 'img/no-image.png')
        else:
            return send_from_directory(app.static_folder, 'favicon.ico')
    except Exception as e:
        print(f"Error serving preview {filename}: {str(e)}")
        return Response("Preview not found", status=404)


# @app.route('/QRCodes/<filename>')
# def qrcode_file(filename):
#     """
#     Serve QR code files from the QRCodes directory.
#     
#     Args:
#         filename (str): Name of the QR code file to serve
#         
#     Returns:
#         flask.Response: The requested QR code file or placeholder image if not found
#     """
#     try:
#         # Check production path first
#         prod_path = "/var/Inventarsystem/Web/QRCodes"
#         dev_path = app.config['QR_CODE_FOLDER']
#         if os.path.exists(os.path.join(prod_path, filename)):
#             return send_from_directory(prod_path, filename)
#         if os.path.exists(os.path.join(dev_path, filename)):
#             return send_from_directory(dev_path, filename)
#             
#             # Use a placeholder image if file not found - first try SVG, then PNG
#             svg_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
#             png_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
#             
#             if os.path.exists(svg_placeholder_path):
#                 return send_from_directory(app.static_folder, 'img/no-image.svg')
#             elif os.path.exists(png_placeholder_path):
#                 return send_from_directory(app.static_folder, 'img/no-image.png')
#             else:
#                 return send_from_directory(app.static_folder, 'favicon.ico')
#     except Exception as e:
#         print(f"Error serving QR code {filename}: {str(e)}")
#         return Response("QR code not found", status=404)


@app.route('/<path:filename>')
def catch_all_files(filename):
    """
    Fallback route to serve files from various directories.
    Tries to find the requested file in known directories.
    
    Args:
        filename (str): Name of the file to serve
        
    Returns:
        flask.Response: The requested file or placeholder image if not found
    """
    try:
        # Check if the file exists in any of our directories
        possible_dirs = [
            app.config['UPLOAD_FOLDER'],
            app.config['THUMBNAIL_FOLDER'],
            app.config['PREVIEW_FOLDER'],
            # app.config['QR_CODE_FOLDER'],  # QR Code serving deactivated
            os.path.join(BASE_DIR, 'static')
        ]
        
        # Check development paths first
        for directory in possible_dirs:
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                return send_from_directory(directory, os.path.basename(filename))
        
        # Check production paths if available
        if os.path.exists("/var/Inventarsystem/Web"):
            prod_dirs = [
                "/var/Inventarsystem/Web/uploads",
                "/var/Inventarsystem/Web/thumbnails",
                "/var/Inventarsystem/Web/previews",
                # "/var/Inventarsystem/Web/QRCodes",  # QR Code serving deactivated
                "/var/Inventarsystem/Web/static"
            ]
            
            for directory in prod_dirs:
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    return send_from_directory(directory, os.path.basename(filename))
        
        # Check if this looks like an image request
        if any(filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'gif', 'svg']):
            # Use a placeholder image if file not found - first try SVG, then PNG
            svg_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
            png_placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
            
            if os.path.exists(svg_placeholder_path):
                return send_from_directory(app.static_folder, 'img/no-image.svg')
            elif os.path.exists(png_placeholder_path):
                return send_from_directory(app.static_folder, 'img/no-image.png')
            else:
                return send_from_directory(app.static_folder, 'favicon.ico')
        
        # If we get here, the file wasn't found
        return Response(f"File {filename} not found", status=404)
    except Exception as e:
        print(f"Error in catch-all route for {filename}: {str(e)}")
        return Response(f"Error serving file: {str(e)}", status=500)


@app.route('/test_connection', methods=['GET'])
def test_connection():
    """
    Test API endpoint to verify the server is running.
    
    Returns:
        dict: Status information including version and status code
    """
    return {'status': 'success', 'message': 'Connection successful', 'version': __version__, 'status_code': 200}


@app.route('/user_status')
def user_status():
    """
    API endpoint to get the current user's status (username, admin status).
    Used by JavaScript in templates to personalize the UI.
    
    Returns:
        JSON: User status information or error if not authenticated
    """
    if 'username' in session:
        is_admin = us.check_admin(session['username'])
        return jsonify({
            'authenticated': True,
            'username': session['username'],
            'is_admin': is_admin
        })
    else:
        return jsonify({
            'authenticated': False,
            'error': 'Not logged in'
        }), 401


@app.route('/')
def home():
    """
    Main route for the application homepage.
    Redirects to the appropriate view based on user role.
    
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    elif not us.check_admin(session['username']):
        return render_template('main.html', username=session['username'])
    else:
        return redirect(url_for('home_admin'))


@app.route('/home_admin')
def home_admin():
    """
    Admin homepage route.
    Only accessible by users with admin privileges.
    
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    return render_template('main_admin.html', username=session['username'])


@app.route('/upload_admin')
def upload_admin():
    """
    Admin upload page route.
    Only accessible by users with admin privileges.
    Supports duplication by passing duplicate_from parameter.
    
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    # Check if this is a duplication request
    duplicate_from = request.args.get('duplicate_from')
    duplicate_flag = request.args.get('duplicate')  # Check for sessionStorage-based duplication
    duplicate_data = None
    
    # Handle the old method (duplicate_from parameter with item ID)
    if duplicate_from:
        try:
            original_item = it.get_item(duplicate_from)
            if original_item:
                # Enhanced debug logging for images
                images = original_item.get('Images', [])
                print(f"DEBUG: Original item: {original_item.get('_id')} has these images: {images}")
                print(f"DEBUG: Images type: {type(images)}, count: {len(images) if isinstance(images, list) else 'not a list'}")
                
                duplicate_data = {
                    'name': original_item.get('Name', ''),
                    'description': original_item.get('Beschreibung', ''),
                    'location': original_item.get('Ort', ''),
                    'room': original_item.get('Raum', ''),
                    'category': original_item.get('Kategorie', ''),
                    'year': original_item.get('Anschaffungsjahr', ''),
                    'cost': original_item.get('Anschaffungskosten', ''),
                    'filter1': original_item.get('Filter1', ''),
                    'filter2': original_item.get('Filter2', ''),
                    'filter3': original_item.get('Filter3', ''),
                    'images': original_item.get('Images', []),
                    'original_id': duplicate_from
                }
                # Copy all filter fields (Filter1_1 through Filter3_5)
                for i in range(1, 4):  # Filter1, Filter2, Filter3
                    for j in range(1, 6):  # _1 through _5
                        filter_key = f'Filter{i}_{j}'
                        if filter_key in original_item:
                            duplicate_data[f'filter{i}_{j}'] = original_item[filter_key]
                
                flash('Element wird dupliziert. Bitte überprüfen Sie die Daten und passen Sie sie bei Bedarf an.', 'info')
            else:
                flash('Ursprungs-Element für Duplizierung nicht gefunden.', 'error')
        except Exception as e:
            print(f"Error loading item for duplication: {e}")
            flash('Fehler beim Laden der Duplizierungsdaten.', 'error')
    
    # Handle the new method (sessionStorage-based duplication)
    elif duplicate_flag == 'true':
        # No server-side processing needed - JavaScript will handle sessionStorage data
        # Just indicate that duplication mode is active
        flash('Element wird dupliziert. Die Daten werden aus dem Session-Speicher geladen.', 'info')
    
    return render_template('upload_admin.html', username=session['username'], duplicate_data=duplicate_data)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login route.
    Authenticates users and redirects to appropriate homepage based on role.
    
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Please fill all fields', 'error')
            return redirect(url_for('login'))
        
        user = us.check_nm_pwd(username, password)

        if user:
            session['username'] = username
            if user['Admin']:
                session['admin'] = True
                return redirect(url_for('home_admin'))
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'error')
            get_flashed_messages()
    return render_template('login.html')


@app.route('/impressum')
def impressum():
    """
    Impressum route.

    Returns:
        flask.Response: Redirect to impressum
    """
    return render_template('impressum.html')

@app.route('/license')
def license():
    """
    License information route.
    Displays the Apache 2.0 license information.

    Returns:
        flask.Response: Rendered license template
    """
    return render_template('license.html')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """
    Change password route.
    Allows users to change their password if logged in.
    
    Returns:
        flask.Response: Rendered form or redirect after password change
    """
    if 'username' not in session:
        flash('Sie müssen angemeldet sein, um Ihr Passwort zu ändern.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not all([current_password, new_password, confirm_password]):
            flash('Bitte füllen Sie alle Felder aus.', 'error')
            return render_template('change_password.html')
            
        if new_password != confirm_password:
            flash('Die neuen Passwörter stimmen nicht überein.', 'error')
            return render_template('change_password.html')
            
        # Verify current password
        user = us.check_nm_pwd(session['username'], current_password)
        if not user:
            flash('Das aktuelle Passwort ist nicht korrekt.', 'error')
            return render_template('change_password.html')
            
        # Check password strength
        if not us.check_password_strength(new_password):
            flash('Das neue Passwort ist zu schwach. Es sollte mindestens 6 Zeichen lang sein.', 'error')
            return render_template('change_password.html')
            
        # Update the password
        if us.update_password(session['username'], new_password):
            flash('Ihr Passwort wurde erfolgreich geändert.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Fehler beim Ändern des Passworts. Bitte versuchen Sie es später erneut.', 'error')
            
    return render_template('change_password.html')

@app.route('/logout')
def logout():
    """
    User logout route.
    Removes user session data and redirects to login.
    
    Returns:
        flask.Response: Redirect to login page
    """
    session.pop('username', None)
    session.pop('admin', None)
    return redirect(url_for('login'))


@app.route('/get_items', methods=['GET'])
def get_items():
    """Return items plus merged favorites (session + DB) and per-item favorite flag."""
    try:
        username = session.get('username')
        # Merge DB favorites into session if logged in
        if username:
            try:
                db_favs = set(us.get_favorites(username))
                session_favs = set(session.get('favorites', []))
                merged = list(db_favs.union(session_favs))
                session['favorites'] = merged
            except Exception as fav_err:
                app.logger.warning(f"Could not merge DB favorites: {fav_err}")
        favorites = set(session.get('favorites', []))

        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        items_col = db['items']
        items_cur = items_col.find()
        items = []
        for itm in items_cur:
            itm['_id'] = str(itm['_id'])
            itm['is_favorite'] = itm['_id'] in favorites
            items.append(itm)
        return jsonify({'items': items, 'favorites': list(favorites)})
    except Exception as e:
        return jsonify({'items': [], 'error': str(e)}), 500


@app.route('/get_item/<id>')
def get_item_json(id):
    try:
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        item = db['items'].find_one({'_id': ObjectId(id)})
        if not item:
            return jsonify({'error': 'not found'}), 404
        item['_id'] = str(item['_id'])
        return jsonify(item)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

"""Favorites management endpoints (persistent + session cache)."""
def _ensure_session_favs():
    if 'favorites' not in session:
        session['favorites'] = []

@app.route('/favorites', methods=['GET'])
def list_favorites():
    _ensure_session_favs()
    username = session.get('username')
    if username:
        try:
            db_favs = set(us.get_favorites(username))
            merged = list(db_favs.union(set(session['favorites'])))
            session['favorites'] = merged
        except Exception as e:
            app.logger.warning(f"Listing favorites merge failed: {e}")
    return jsonify({'ok': True, 'favorites': session['favorites']})

@app.route('/favorites/<item_id>', methods=['POST'])
def add_fav(item_id):
    _ensure_session_favs()
    if item_id not in session['favorites']:
        session['favorites'].append(item_id)
    username = session.get('username')
    if username:
        try:
            us.add_favorite(username, item_id)
        except Exception as e:
            app.logger.warning(f"Persist add favorite failed: {e}")
    session.modified = True
    return jsonify({'ok': True, 'favorites': session['favorites']})

@app.route('/favorites/<item_id>', methods=['DELETE'])
def remove_fav(item_id):
    _ensure_session_favs()
    session['favorites'] = [f for f in session['favorites'] if f != item_id]
    username = session.get('username')
    if username:
        try:
            us.remove_favorite(username, item_id)
        except Exception as e:
            app.logger.warning(f"Persist remove favorite failed: {e}")
    session.modified = True
    return jsonify({'ok': True, 'favorites': session['favorites']})

@app.route('/debug/favorites')
def debug_favorites():
    """Diagnostic endpoint: shows session favorites, DB favorites and merged output."""
    username = session.get('username')
    session_favs = list(session.get('favorites', []))
    db_favs = []
    if username:
        try:
            db_favs = us.get_favorites(username)
        except Exception as e:
            return jsonify({'ok': False, 'error': f'db_error: {e}', 'session': session_favs})
    merged = sorted(set(session_favs) | set(db_favs))
    return jsonify({'ok': True, 'user': username, 'session': session_favs, 'db': db_favs, 'merged': merged})


@app.route('/upload_item', methods=['POST'])
def upload_item():
    """
    Route for adding new items to the inventory.
    Handles file uploads and creates QR codes.
    Enhanced for mobile browser compatibility.
    
    Returns:
        flask.Response: Redirect to admin homepage or JSON response
    """
    # Check if the user is authenticated
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
        
    # Check if user is an admin
    username = session['username']
    if not us.check_admin(username):
        return jsonify({'success': False, 'message': 'Admin rights required'}), 403
        
    # Detect if request is from mobile device
    is_mobile = 'Mobile' in request.headers.get('User-Agent', '')
    is_ios = 'iPhone' in request.headers.get('User-Agent', '') or 'iPad' in request.headers.get('User-Agent', '')
    
    # Log mobile request for debugging
    if is_mobile:
        app.logger.info(f"Mobile upload from {request.headers.get('User-Agent', 'unknown')} by {username}")
    
    try:
        # Strip whitespace from all text fields
        name = strip_whitespace(request.form['name'])
        ort = strip_whitespace(request.form['ort'])
        beschreibung = strip_whitespace(request.form['beschreibung'])
        
        # Check both possible image field names
        images = request.files.getlist('images') or request.files.getlist('new_images')
        
        filter_upload = strip_whitespace(request.form.getlist('filter'))
        filter_upload2 = strip_whitespace(request.form.getlist('filter2'))
        filter_upload3 = strip_whitespace(request.form.getlist('filter3'))
        anschaffungs_jahr = strip_whitespace(request.form.getlist('anschaffungsjahr'))
        anschaffungs_kosten = strip_whitespace(request.form.getlist('anschaffungskosten'))
        code_4 = strip_whitespace(request.form.getlist('code_4'))
        
        # Check if this is a duplication
        is_duplicating = request.form.get('is_duplicating') == 'true'
        
        # Get duplicate_images if duplicating
        duplicate_images = request.form.getlist('duplicate_images') if is_duplicating else []
        print(f"DEBUG: Duplicate images from form: {duplicate_images}, count: {len(duplicate_images)}")
        
        # Make sure duplicate_images is always a list, even if there's only one
        if is_duplicating and duplicate_images and not isinstance(duplicate_images, list):
            duplicate_images = [duplicate_images]
        
        # Log details about each image
        if is_duplicating and duplicate_images:
            for i, img in enumerate(duplicate_images):
                print(f"DEBUG: Duplicate image {i+1}/{len(duplicate_images)}: {img}")
        
        # Get book cover image if downloaded
        book_cover_image = request.form.get('book_cover_image')
        
        # Special handling for mobile browsers that might send data differently
        if is_mobile and 'mobile_data' in request.form:
            try:
                mobile_data = json.loads(request.form['mobile_data'])
                # Override values with mobile data if available
                if 'filters' in mobile_data:
                    filter_upload = mobile_data.get('filters', [])
                if 'filters2' in mobile_data:
                    filter_upload2 = mobile_data.get('filters2', [])
                if 'filters3' in mobile_data:
                    filter_upload3 = mobile_data.get('filters3', [])
                if 'duplicate_images' in mobile_data and mobile_data['duplicate_images']:
                    duplicate_images = mobile_data.get('duplicate_images', [])
            except json.JSONDecodeError as e:
                app.logger.error(f"Error parsing mobile data: {str(e)}")
    except Exception as e:
        error_msg = f"Error processing form data: {str(e)}"
        app.logger.error(error_msg)
        if is_mobile:
            return jsonify({'success': False, 'message': error_msg}), 400
        else:
            flash('Fehler beim Verarbeiten der Formulardaten. Bitte versuchen Sie es erneut.', 'error')
            return redirect(url_for('home_admin'))

    # Validation
    if not name or not ort or not beschreibung:
        error_msg = 'Bitte füllen Sie alle erforderlichen Felder aus'
        if is_mobile:
            return jsonify({'success': False, 'message': error_msg}), 400
        else:
            flash(error_msg, 'error')
            return redirect(url_for('home_admin'))

    # Only check for images if not duplicating and no duplicate images provided and no book cover
    if not is_duplicating and not images and not duplicate_images and not book_cover_image:
        error_msg = 'Bitte laden Sie mindestens ein Bild hoch'
        if is_mobile:
            return jsonify({'success': False, 'message': error_msg}), 400
        else:
            flash(error_msg, 'error')
            return redirect(url_for('home_admin'))

    # Check if code is unique
    if code_4 and not it.is_code_unique(code_4[0]):
        error_msg = 'Der Code wird bereits verwendet. Bitte wählen Sie einen anderen Code.'
        if is_mobile:
            return jsonify({'success': False, 'message': error_msg}), 400
        else:
            flash(error_msg, 'error')
            return redirect(url_for('home_admin'))

    # Process any new uploaded images with robust error handling
    image_filenames = []
    processed_count = 0
    error_count = 0
    skipped_count = 0
    
    # Create a structured log entry for upload session
    upload_session_id = str(uuid.uuid4())[:8]
    app.logger.info(f"Starting image upload session {upload_session_id} - Files: {len(images)}, User: {username}")
    
    # Ensure all required directories exist
    for directory in [app.config['UPLOAD_FOLDER'], app.config['THUMBNAIL_FOLDER'], app.config['PREVIEW_FOLDER']]:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            app.logger.error(f"Failed to create directory {directory}: {str(e)}")
    
    # Process each image independently
    for index, image in enumerate(images):
        image_log_prefix = f"[Upload {upload_session_id}][Image {index+1}/{len(images)}]"
        
        if not image or not image.filename or image.filename == '':
            app.logger.warning(f"{image_log_prefix} Empty file or filename")
            skipped_count += 1
            continue
            
        # Get file extension for special handling
        _, file_ext = os.path.splitext(image.filename.lower())
        is_png = file_ext.lower() == '.png'
        
        if is_png:
            app.logger.info(f"PNG DEBUG: {image_log_prefix} Detected PNG file: {image.filename}")
            # Check file size
            image.seek(0, os.SEEK_END)
            file_size = image.tell() / (1024 * 1024)  # Size in MB
            image.seek(0)  # Reset file pointer
            app.logger.info(f"PNG DEBUG: {image_log_prefix} PNG file size: {file_size:.2f}MB")
            
            # Check first few bytes for PNG signature and analyze header
            header_bytes = image.read(64)  # Read more for thorough analysis
            image.seek(0)  # Reset pointer
            png_signature = b'\x89PNG\r\n\x1a\n'
            is_valid_signature = header_bytes.startswith(png_signature)
            
            # Create a hex dump of header for debugging
            hex_dump = ' '.join([f"{b:02x}" for b in header_bytes[:32]])
            app.logger.info(f"PNG DEBUG: {image_log_prefix} PNG header hex: {hex_dump}")
            app.logger.info(f"PNG DEBUG: {image_log_prefix} PNG signature valid: {is_valid_signature}, bytes: {header_bytes[:8]!r}")
            
            # Analyze PNG chunks if signature is valid
            if is_valid_signature:
                try:
                    # Look for IHDR chunk that should follow the signature
                    if header_bytes[8:12] == b'IHDR':
                        # Extract width and height from IHDR chunk (bytes 16-23)
                        import struct
                        width = struct.unpack('>I', header_bytes[16:20])[0]
                        height = struct.unpack('>I', header_bytes[20:24])[0]
                        bit_depth = header_bytes[24]
                        color_type = header_bytes[25]
                        app.logger.info(f"PNG DEBUG: {image_log_prefix} PNG dimensions from header: {width}x{height}, bit depth: {bit_depth}, color type: {color_type}")
                    else:
                        app.logger.warning(f"PNG DEBUG: {image_log_prefix} Expected IHDR chunk not found. Found: {header_bytes[8:12]!r}")
                except Exception as chunk_err:
                    app.logger.error(f"PNG DEBUG: {image_log_prefix} Error analyzing PNG chunks: {str(chunk_err)}")
            else:
                app.logger.error(f"PNG DEBUG: {image_log_prefix} Invalid PNG signature!")
        
        app.logger.info(f"{image_log_prefix} Processing: {image.filename}")
        
        try:
            # Comprehensive file validation with detailed logging
            is_allowed, error_message = allowed_file(image.filename, image, max_size_mb=cfg.IMAGE_MAX_UPLOAD_MB)
            
            if not is_allowed:
                app.logger.warning(f"{image_log_prefix} Validation failed: {error_message}")
                if is_png:
                    app.logger.error(f"PNG DEBUG: {image_log_prefix} PNG validation failed: {error_message}")
                skipped_count += 1
                if not is_mobile:
                    flash(error_message, 'error')
                continue
                
            # Get the file extension for content type determination
            secure_name = secure_filename(image.filename)
            _, ext_part = os.path.splitext(secure_name)
            is_png = ext_part.lower() == '.png'
            
            # Generate a completely unique filename using UUID
            unique_id = str(uuid.uuid4())
            timestamp = time.strftime("%Y%m%d%H%M%S")
            
            # New filename format with UUID to ensure uniqueness
            saved_filename = f"{unique_id}_{timestamp}{ext_part}"
            app.logger.info(f"{image_log_prefix} Assigned unique filename: {saved_filename}")
            
            if is_png:
                app.logger.info(f"PNG DEBUG: {image_log_prefix} Creating PNG with filename: {saved_filename}")
            
            # For iOS devices, we need special handling for the file save
            if is_ios:
                app.logger.info(f"{image_log_prefix} Using iOS-specific file handling")
                # Save to a temporary file first to avoid iOS stream issues
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{saved_filename}")
                
                try:
                    if is_png:
                        app.logger.info(f"PNG DEBUG: {image_log_prefix} Using iOS PNG save method")
                        # Before saving, verify the file content again
                        try:
                            image.seek(0)
                            pre_save_data = image.read(16)
                            image.seek(0)
                            pre_save_hex = ' '.join([f"{b:02x}" for b in pre_save_data])
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Pre-save data: {pre_save_hex}")
                        except Exception as pre_err:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Error checking pre-save data: {str(pre_err)}")
                    
                    # For PNGs, try a direct binary save first
                    if is_png:
                        try:
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Attempting binary save for iOS PNG")
                            image.seek(0)
                            png_data = image.read()
                            with open(temp_path, 'wb') as f:
                                f.write(png_data)
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Binary write complete, size: {len(png_data)} bytes")
                        except Exception as bin_err:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Binary write failed: {str(bin_err)}")
                            # Fall back to normal save
                            image.seek(0)
                            image.save(temp_path)
                    else:
                        image.save(temp_path)
                    
                    # Validate the saved file
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        if is_png:
                            file_size = os.path.getsize(temp_path)
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Temp PNG file saved successfully: {file_size/1024:.1f}KB")
                            
                            # Verify it's a valid PNG
                            try:
                                with open(temp_path, 'rb') as f:
                                    png_header = f.read(16)
                                    png_signature = b'\x89PNG\r\n\x1a\n'
                                    is_valid = png_header.startswith(png_signature)
                                    
                                    header_hex = ' '.join([f"{b:02x}" for b in png_header])
                                    app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved file header: {header_hex}")
                                    
                                    if not is_valid:
                                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Invalid PNG signature in saved file!")
                                    else:
                                        app.logger.info(f"PNG DEBUG: {image_log_prefix} Valid PNG signature confirmed in saved file")
                                        
                                    # Try opening with PIL to confirm it's valid
                                    try:
                                        with Image.open(temp_path) as img:
                                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved PNG validates with PIL: {img.format} {img.size}")
                                    except Exception as pil_err:
                                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Saved PNG fails PIL validation: {str(pil_err)}")
                                        
                            except Exception as verify_err:
                                app.logger.error(f"PNG DEBUG: {image_log_prefix} Error verifying PNG: {str(verify_err)}")
                        
                        # Rename to the final filename
                        final_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                        os.rename(temp_path, final_path)
                        app.logger.info(f"{image_log_prefix} Successfully saved via iOS handler: {os.path.getsize(final_path)/1024:.1f}KB")
                    else:
                        if is_png:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Failed to save temp PNG file (zero size or missing)")
                        raise Exception("Failed to save image file (zero size or missing)")
                except Exception as e:
                    app.logger.error(f"{image_log_prefix} iOS save failed: {str(e)}")
                    if is_png:
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} iOS PNG save failed: {str(e)}")
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Error type: {type(e).__name__}")
                        # Log full traceback for PNG errors
                        import io
                        tb_output = io.StringIO()
                        traceback.print_exc(file=tb_output)
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Full traceback:\n{tb_output.getvalue()}")
                    
                    # Try regular save as fallback
                    try:
                        image.seek(0)  # Reset file pointer
                        if is_png:
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Attempting fallback PNG save method")
                        
                        image.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
                        app.logger.info(f"{image_log_prefix} Fallback save successful")
                        
                        if is_png:
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Fallback PNG save successful")
                    except Exception as fallback_err:
                        app.logger.error(f"{image_log_prefix} Fallback save also failed: {str(fallback_err)}")
                        if is_png:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Fallback PNG save also failed: {str(fallback_err)}")
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Error type: {type(fallback_err).__name__}")
                            traceback.print_exc()
                        error_count += 1
                        continue
            else:
                # Regular file save for non-iOS devices
                try:
                    if is_png:
                        app.logger.info(f"PNG DEBUG: {image_log_prefix} Using standard PNG save method")
                        
                        # Check file content before saving
                        try:
                            image.seek(0)
                            pre_save_data = image.read(16)
                            image.seek(0)
                            pre_save_hex = ' '.join([f"{b:02x}" for b in pre_save_data])
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Pre-save data: {pre_save_hex}")
                            
                            # Check if it's really a PNG
                            png_signature = b'\x89PNG\r\n\x1a\n'
                            if not pre_save_data.startswith(png_signature):
                                app.logger.error(f"PNG DEBUG: {image_log_prefix} File does not have valid PNG signature before save!")
                        except Exception as pre_err:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Error checking pre-save data: {str(pre_err)}")
                        
                        # Try an alternative saving method for PNGs with detailed error tracking
                        try:
                            # Read the image data directly
                            image.seek(0)
                            image_data = image.read()
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Read {len(image_data)} bytes of PNG data")
                            
                            # Write it manually to file
                            save_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                            with open(save_path, 'wb') as f:
                                f.write(image_data)
                            
                            file_size = os.path.getsize(save_path)
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Direct binary PNG write successful: {file_size/1024:.1f}KB")
                            
                            # Verify the saved file
                            try:
                                with open(save_path, 'rb') as f:
                                    saved_header = f.read(16)
                                    header_hex = ' '.join([f"{b:02x}" for b in saved_header])
                                    app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved PNG header: {header_hex}")
                                    
                                    is_valid = saved_header.startswith(png_signature)
                                    app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved PNG has valid signature: {is_valid}")
                                    
                                    if is_valid:
                                        # Additional validation with PIL
                                        try:
                                            with Image.open(save_path) as img:
                                                app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved PNG validates with PIL: {img.format} {img.size}")
                                        except Exception as pil_err:
                                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Saved PNG fails PIL validation: {str(pil_err)}")
                            except Exception as verify_err:
                                app.logger.error(f"PNG DEBUG: {image_log_prefix} Error verifying saved PNG: {str(verify_err)}")
                            
                        except Exception as png_write_err:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Direct PNG write failed: {str(png_write_err)}")
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Error type: {type(png_write_err).__name__}")
                            
                            # Log traceback for PNG errors
                            import io
                            tb_output = io.StringIO()
                            traceback.print_exc(file=tb_output)
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Binary write traceback:\n{tb_output.getvalue()}")
                            
                            # Fall back to standard method
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Attempting standard PIL save method")
                            image.seek(0)
                            image.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
                    else:
                        # Standard save for non-PNG files
                        image.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
                    
                    app.logger.info(f"{image_log_prefix} Standard save successful")
                except Exception as save_err:
                    app.logger.error(f"{image_log_prefix} Failed to save file: {str(save_err)}")
                    if is_png:
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Standard PNG save failed: {str(save_err)}")
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Error type: {type(save_err).__name__}")
                        
                        # Log traceback for PNG errors
                        import io
                        tb_output = io.StringIO()
                        traceback.print_exc(file=tb_output)
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Standard save traceback:\n{tb_output.getvalue()}")
                        
                        # Try one last method - save as a different format
                        try:
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Attempting last resort conversion to JPG")
                            image.seek(0)
                            
                            # Try to convert PNG to JPG as a last resort
                            with Image.open(image) as img:
                                rgb_img = img.convert('RGB')
                                jpg_path = os.path.splitext(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))[0] + '.jpg'
                                rgb_img.save(jpg_path, 'JPEG')
                                app.logger.info(f"PNG DEBUG: {image_log_prefix} Successfully saved as JPG instead: {jpg_path}")
                                # Update the saved_filename to reflect the new extension
                                saved_filename = os.path.basename(jpg_path)
                        except Exception as jpg_err:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} Final JPG conversion failed: {str(jpg_err)}")
                            
                        traceback.print_exc()
                    error_count += 1
                    continue
            
            # Verify the file was saved correctly
            saved_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
            if not os.path.exists(saved_path) or os.path.getsize(saved_path) == 0:
                app.logger.error(f"{image_log_prefix} Saved file is missing or empty: {saved_path}")
                if is_png:
                    app.logger.error(f"PNG DEBUG: {image_log_prefix} Saved PNG is missing or empty: {saved_path}")
                error_count += 1
                continue
            
            # Special verification for PNG files
            if is_png:
                try:
                    app.logger.info(f"PNG DEBUG: {image_log_prefix} Verifying saved PNG: {saved_path}")
                    saved_size = os.path.getsize(saved_path) / 1024.0  # in KB
                    app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved PNG size: {saved_size:.1f}KB")
                    
                    # Check file integrity by trying to open it
                    try:
                        with Image.open(saved_path) as img:
                            png_width, png_height = img.size
                            png_mode = img.mode
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Saved PNG valid: {png_width}x{png_height}, mode: {png_mode}")
                    except Exception as png_verify_err:
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} PNG verification failed: {str(png_verify_err)}")
                        
                        # Try to fix by copying from the original
                        try:
                            image.seek(0)
                            with open(saved_path, 'wb') as f:
                                f.write(image.read())
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Attempted to fix PNG by direct copy")
                        except Exception as png_fix_err:
                            app.logger.error(f"PNG DEBUG: {image_log_prefix} PNG fix attempt failed: {str(png_fix_err)}")
                except Exception as e:
                    app.logger.error(f"PNG DEBUG: {image_log_prefix} PNG verification error: {str(e)}")
            
            # Generate optimized versions (thumbnails and previews)
            optimization_success = False
            try:
                # Log original file size before optimization
                original_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                original_size = os.path.getsize(original_path)
                
                # Get original image dimensions
                original_dimensions = "unknown"
                try:
                    with Image.open(original_path) as img:
                        original_dimensions = f"{img.width}x{img.height}"
                        if is_png:
                            app.logger.info(f"PNG DEBUG: {image_log_prefix} Original PNG dimensions: {original_dimensions}, mode: {img.mode}")
                except Exception as dim_err:
                    app.logger.warning(f"{image_log_prefix} Could not get image dimensions: {str(dim_err)}")
                    if is_png:
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Could not get PNG dimensions: {str(dim_err)}")
                        app.logger.error(f"PNG DEBUG: {image_log_prefix} Error type: {type(dim_err).__name__}")
                        traceback.print_exc()
                
                app.logger.info(f"{image_log_prefix} Starting optimization for {saved_filename} ({original_size/1024:.1f}KB, {original_dimensions})")
                
                # PNG-specific optimization options
                if is_png:
                    app.logger.info(f"PNG DEBUG: {image_log_prefix} Starting PNG optimization")
                    # For PNGs, we might need different parameters
                    optimization_result = generate_optimized_versions(
                        saved_filename, 
                        max_original_width=500, 
                        target_size_kb=100,  # Higher target for PNGs to maintain transparency
                        debug_prefix=f"PNG DEBUG: {image_log_prefix}"
                    )
                else:
                    # Standard optimization for non-PNG images
                    optimization_result = generate_optimized_versions(saved_filename, max_original_width=500, target_size_kb=80)
                
                # Log file size after optimization
                optimized_name = os.path.splitext(saved_filename)[0] + '.jpg'
                optimized_path = os.path.join(app.config['UPLOAD_FOLDER'], optimized_name)
                
                if os.path.exists(optimized_path):
                    optimized_size = os.path.getsize(optimized_path)
                    reduction = (1 - (optimized_size / original_size)) * 100 if original_size > 0 else 0
                    
                    # Get optimized dimensions
                    optimized_dimensions = "unknown"
                    try:
                        with Image.open(optimized_path) as img:
                            optimized_dimensions = f"{img.width}x{img.height}"
                    except Exception as dim_err:
                        app.logger.warning(f"{image_log_prefix} Could not get optimized dimensions: {str(dim_err)}")
                        
                    app.logger.info(
                        f"{image_log_prefix} Optimization results:\n"
                        f"  File: {saved_filename} → {optimized_name}\n"
                        f"  Size: {original_size/1024:.1f}KB → {optimized_size/1024:.1f}KB ({reduction:.1f}% reduction)\n"
                        f"  Dimensions: {original_dimensions} → {optimized_dimensions}"
                    )
                    optimization_success = True
                else:
                    app.logger.warning(f"{image_log_prefix} Optimized file not found: {optimized_path}")
            except Exception as e:
                app.logger.error(f"{image_log_prefix} Optimization failed: {str(e)}")
                traceback.print_exc()
                
                # Try a simplified optimization fallback if the full one fails
                try:
                    app.logger.info(f"{image_log_prefix} Attempting simplified thumbnail generation as fallback")
                    # Simply create thumbnails directly from original without full optimization
                    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], os.path.splitext(saved_filename)[0] + '_thumb.jpg')
                    preview_path = os.path.join(app.config['PREVIEW_FOLDER'], os.path.splitext(saved_filename)[0] + '_preview.jpg')
                    
                    with Image.open(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)) as img:
                        # Make a small thumbnail
                        img.thumbnail((150, 150))
                        img.save(thumbnail_path, 'JPEG', quality=85)
                        
                        # Make a medium preview
                        img = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
                        img.thumbnail((300, 300))
                        img.save(preview_path, 'JPEG', quality=85)
                        
                    app.logger.info(f"{image_log_prefix} Fallback thumbnail generation successful")
                except Exception as fallback_err:
                    app.logger.error(f"{image_log_prefix} Fallback thumbnail generation also failed: {str(fallback_err)}")
            
            # Always add the filename to our list even if optimization failed
            # We'll use the original in that case
            image_filenames.append(saved_filename)
            processed_count += 1
            app.logger.info(f"{image_log_prefix} Successfully processed")
            
        except Exception as e:
            app.logger.error(f"{image_log_prefix} Unexpected error: {str(e)}")
            traceback.print_exc()
            error_count += 1
            # Continue with the next image
    
    # Log summary of upload session
    app.logger.info(f"Upload session {upload_session_id} completed: {processed_count} processed, {error_count} errors, {skipped_count} skipped")

    # Handle duplicate images if duplicating
    if duplicate_images:
        app.logger.info(f"Processing {len(duplicate_images)} duplicate images: {duplicate_images}")
        
        # For mobile browsers, we need to verify the duplicate images exist first
        verified_duplicates = []
        for dup_img in duplicate_images:
            # Try looking in different paths
            # Add all possible paths where images might be stored
            dev_upload_path = app.config['UPLOAD_FOLDER']
            prod_upload_path = '/var/Inventarsystem/Web/uploads'
            
            # Also look for image variations with suffixes that might be in the path
            name_part, ext_part = os.path.splitext(dup_img)
            possible_filenames = [
                dup_img,
                f"{name_part}.jpg",  # In case it was converted to JPG
                f"{name_part}.png",  # In case it was saved as PNG
            ]
            
            possible_paths = []
            for filename in possible_filenames:
                possible_paths.extend([
                    os.path.join(dev_upload_path, filename),  # Development upload path
                    os.path.join(prod_upload_path, filename),  # Production upload path
                ])
            
            app.logger.info(f"Looking for duplicate image {dup_img} in paths: {possible_paths}")
            
            # Try to find the original image
            found = False
            for path in possible_paths:
                if os.path.exists(path) and os.path.isfile(path):
                    verified_duplicates.append((dup_img, path))
                    app.logger.info(f"Found duplicate image at: {path}")
                    found = True
                    break
            
            if not found:
                app.logger.warning(f"Duplicate image not found: {dup_img}")
                # Try to find any image with a similar filename (removing size or resolution parts)
                # This handles cases where the filename may have variations like "_800" suffix
                base_name = os.path.splitext(dup_img)[0]
                base_name = re.sub(r'_\d+$', '', base_name)  # Remove trailing _NUMBER
                
                if len(base_name) > 5:  # Only if we have a meaningful base name
                    app.logger.info(f"Trying to find similar images with base name: {base_name}")
                    
                    # Search in development directory
                    dev_files = os.listdir(app.config['UPLOAD_FOLDER']) if os.path.exists(app.config['UPLOAD_FOLDER']) else []
                    # Search in production directory
                    prod_path = "/var/Inventarsystem/Web/uploads"
                    prod_files = os.listdir(prod_path) if os.path.exists(prod_path) else []
                    
                    # Combine all files
                    all_files = dev_files + prod_files
                    
                    # Find similar files
                    for f in all_files:
                        if base_name in f:
                            img_path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                            if not os.path.exists(img_path):
                                img_path = os.path.join(prod_path, f)
                            
                            if os.path.exists(img_path) and os.path.isfile(img_path):
                                app.logger.info(f"Found similar image: {f} at {img_path}")
                                verified_duplicates.append((f, img_path))
                                found = True
                                break
                
                # If we still can't find anything, just use a placeholder
                if not found:
                    app.logger.warning(f"Could not find any similar image for: {dup_img}, will use placeholder")
        
        # Create copies of verified images with new unique filenames
        duplicate_image_copies = []
        
        # Create a placeholder name for each image that wasn't found
        placeholder_used = False
        original_count = len(duplicate_images)
        
        # Process each original image - either use found file or placeholder
        for i, dup_img in enumerate(duplicate_images):
            # Look for corresponding verified image
            found_image = None
            for verified_img, src_path in verified_duplicates:
                if verified_img == dup_img:
                    found_image = (verified_img, src_path)
                    break
            
            try:
                # Generate a new unique filename (same for real or placeholder)
                unique_id = str(uuid.uuid4())
                timestamp = time.strftime("%Y%m%d%H%M%S")
                _, ext_part = os.path.splitext(dup_img) if dup_img else '.jpg'
                new_filename = f"{unique_id}_{timestamp}{ext_part}"
                
                # If we found the image, copy it
                if found_image:
                    dup_img, src_path = found_image
                    app.logger.info(f"Copying image {i+1}/{original_count} from {src_path} to {new_filename}")
                    
                    # Copy the image file to the new name
                    dst_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    
                    # Make sure the target directory exists
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(src_path, dst_path)
                    
                    # Verify the file was copied successfully
                    if os.path.exists(dst_path):
                        app.logger.info(f"Successfully copied image to {dst_path}")
                    else:
                        app.logger.error(f"Failed to copy image to {dst_path}")
                        # If copy fails, use placeholder
                        raise Exception("Copy failed - will use placeholder")
                    
                    # Generate optimized versions (thumbnails and previews) for the new copy
                    try:
                        result = generate_optimized_versions(new_filename, max_original_width=500, target_size_kb=80)
                        app.logger.info(f"Generated optimized versions: {result}")
                    except Exception as e:
                        app.logger.error(f"Error generating optimized versions for {new_filename}: {e}")
                        # If optimization fails, at least keep the original file
                        result = {'original': new_filename}
                        traceback.print_exc()
                
                # If we didn't find the image, use a placeholder
                else:
                    app.logger.warning(f"Using placeholder for image {i+1}/{original_count} (original: {dup_img})")
                    
                    # Copy placeholder to uploads directory with the new filename
                    placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
                    if not os.path.exists(placeholder_path):
                        placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
                    
                    if os.path.exists(placeholder_path):
                        dst_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                        shutil.copy2(placeholder_path, dst_path)
                        app.logger.info(f"Copied placeholder image to {dst_path}")
                        placeholder_used = True
                        
                        # Skip the optimization step for placeholder images
                        # Just add directly to the list of image filenames
                        continue
                    else:
                        app.logger.error(f"Placeholder image not found at {placeholder_path}")
                        # Create a simple placeholder file
                        with open(os.path.join(app.config['UPLOAD_FOLDER'], new_filename), 'w') as f:
                            f.write("Placeholder")
                        placeholder_used = True
                        # Skip the optimization step
                        continue
                
                # Add the new filename to our list (either copied or placeholder)
                duplicate_image_copies.append(new_filename)
                processed_count += 1
                
                app.logger.info(f"Processed image {i+1}/{original_count}: {new_filename}")
            except Exception as e:
                app.logger.error(f"Error processing image {i+1}/{original_count} ({dup_img}): {str(e)}")
                traceback.print_exc()
                error_count += 1
        
        # Log placeholder usage
        if placeholder_used:
            app.logger.warning(f"Used placeholders for some missing images during duplication")
        
        # Log if no images were processed
        if not duplicate_image_copies:
            app.logger.warning(f"No duplicate images were processed")
            if duplicate_images:
                app.logger.warning(f"Original had {len(duplicate_images)} images, but none were copied")
        
        # Add the new image copies to our list of filenames
        image_filenames.extend(duplicate_image_copies)

    # Handle book cover image if provided
    if book_cover_image:
        # Verify the book cover image exists
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], book_cover_image)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            # Create a unique filename for the book cover
            unique_id = str(uuid.uuid4())
            timestamp = time.strftime("%Y%m%d%H%M%S")
            _, ext_part = os.path.splitext(book_cover_image)
            
            new_filename = f"{unique_id}_{timestamp}_book_cover{ext_part}"
            new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            
            # Copy the file to the new unique name
            shutil.copy2(full_path, new_path)
            
            # Use the new filename instead
            image_filenames.append(new_filename)
            app.logger.info(f"Copied book cover from {book_cover_image} to {new_filename}")
        else:
            app.logger.warning(f"Book cover image not found: {book_cover_image}")
    
    # Log image processing stats
    app.logger.info(f"Upload stats: processed={processed_count}, errors={error_count}, skipped={skipped_count}, duplicates={len(duplicate_images) if duplicate_images else 0}")
    
    # If location is not in the predefined list, add it
    predefined_locations = it.get_predefined_locations()
    if ort and ort not in predefined_locations:
        it.add_predefined_location(ort)
    
    # Add the item to the database
    item_id = it.add_item(name, ort, beschreibung, image_filenames, filter_upload, 
                        filter_upload2, filter_upload3, 
                        anschaffungs_jahr[0] if anschaffungs_jahr else None, 
                        anschaffungs_kosten[0] if anschaffungs_kosten else None,
                        code_4[0] if code_4 else None)
    
    if item_id:
    # Create QR code for the item (deactivated)
    # create_qr_code(str(item_id))
        success_msg = 'Element wurde erfolgreich hinzugefügt'
        
        if is_mobile:
            return jsonify({
                'success': True, 
                'message': success_msg,
                'itemId': str(item_id),
                'stats': {
                    'processed': processed_count,
                    'errors': error_count,
                    'skipped': skipped_count,
                    'duplicates': len(duplicate_images) if duplicate_images else 0,
                    'totalImages': len(image_filenames)
                }
            })
        else:
            flash(success_msg, 'success')
            return redirect(url_for('home_admin', highlight_item=str(item_id)))
    else:
        error_msg = 'Fehler beim Hinzufügen des Elements'
        if is_mobile:
            return jsonify({'success': False, 'message': error_msg}), 500
        else:
            flash(error_msg, 'error')
            return redirect(url_for('home_admin'))


@app.route('/duplicate_item', methods=['POST'])
def duplicate_item():
    """
    Route for duplicating an existing item.
    Returns JSON response with success status.
    Enhanced for mobile browser compatibility.
    
    Returns:
        flask.Response: JSON response with success status and data
    """
    try:
        # Check authentication
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Nicht angemeldet'}), 401
        
        # Check if user is admin
        username = session['username']
        if not us.check_admin(username):
            return jsonify({'success': False, 'message': 'Keine Administratorrechte'}), 403
        
        # Detect if request is from mobile device
        is_mobile = 'Mobile' in request.headers.get('User-Agent', '')
        is_ios = 'iPhone' in request.headers.get('User-Agent', '') or 'iPad' in request.headers.get('User-Agent', '')
        
        # Log mobile duplication for debugging
        if is_mobile:
            app.logger.info(f"Mobile duplication from {request.headers.get('User-Agent', 'unknown')} by {username}")
        
        # Get original item ID
        original_item_id = request.form.get('original_item_id')
        if not original_item_id:
            return jsonify({'success': False, 'message': 'Ursprungs-Element-ID fehlt'}), 400
        
        # Fetch original item data
        original_item = it.get_item(original_item_id)
        if not original_item:
            return jsonify({'success': False, 'message': 'Ursprungs-Element nicht gefunden'}), 404
        
        # Process filters as arrays (same as stored in database)
        filter1_array = original_item.get('Filter', [])
        filter2_array = original_item.get('Filter2', [])
        filter3_array = original_item.get('Filter3', [])
        
        # Ensure filters are arrays
        if not isinstance(filter1_array, list):
            filter1_array = [filter1_array] if filter1_array else []
        if not isinstance(filter2_array, list):
            filter2_array = [filter2_array] if filter2_array else []
        if not isinstance(filter3_array, list):
            filter3_array = [filter3_array] if filter3_array else []
            
        # Verify image paths for mobile devices to avoid issues with non-existent images
        images = original_item.get('Images', [])
        verified_images = []
        
        if is_mobile:
            for img in images:
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], img)
                if os.path.exists(img_path) and os.path.isfile(img_path):
                    verified_images.append(img)
                else:
                    app.logger.warning(f"Image not found for duplication: {img}")
            
            # If we lost images in verification, log it
            if len(verified_images) < len(images):
                app.logger.warning(f"Only {len(verified_images)} of {len(images)} images verified for mobile duplication")
        else:
            verified_images = images

        # For iOS devices, add more diagnostics and reduce data size if needed
        if is_ios:
            # Check if images have thumbnail versions to use for preview instead of full images
            thumbnails_exist = []
            for img in verified_images[:5]:  # Only check first 5 to save time
                thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], img.replace('_thumb', '') + '_thumb')
                if os.path.exists(thumb_path):
                    thumbnails_exist.append(True)
                else:
                    thumbnails_exist.append(False)
            
            # Log detailed diagnostics
            app.logger.info(f"iOS duplication details: {len(verified_images)} images, "
                           f"thumbnails available: {all(thumbnails_exist)}, "
                           f"filter sizes: {len(filter1_array)}, {len(filter2_array)}, {len(filter3_array)}")
                           
        return jsonify({
            'success': True, 
            'message': 'Duplication data prepared successfully',
            'item_data': {
                'name': original_item.get('Name', ''),
                'description': original_item.get('Beschreibung', ''),
                'location': original_item.get('Ort', ''),
                'room': original_item.get('Raum', ''),
                'category': original_item.get('Kategorie', ''),
                'year': original_item.get('Anschaffungsjahr', ''),
                'cost': original_item.get('Anschaffungskosten', ''),
                'filter1': filter1_array,
                'filter2': filter2_array,
                'filter3': filter3_array,
                'images': verified_images,  # Using verified images instead of original
                'isMobile': is_mobile,
                'isIOS': is_ios
            }
        })
        
    except Exception as e:
        print(f"Error in duplicate_item: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Serverfehler beim Duplizieren'}), 500


@app.route('/delete_item/<id>', methods=['POST', 'GET'])
def delete_item(id):
    """
    Route for deleting inventory items.
    
    Args:
        id (str): ID of the item to delete
        
    Returns:
        flask.Response: Redirect to admin homepage
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    
    # Delete associated images first
    item_to_delete = it.get_item(id)
    if not item_to_delete:
        flash('Item not found.', 'error')
        return redirect(url_for('home_admin'))
    
    image_filenames = item_to_delete.get('Images', [])
    
    # Attempt to delete image files
    try:
        stats = delete_item_images(image_filenames)
        app.logger.info(f"Item {id} deletion - Images removed: " +
                      f"originals={stats['originals']}, thumbnails={stats['thumbnails']}, " +
                      f"previews={stats['previews']}, errors={stats['errors']}")
    except Exception as e:
        app.logger.error(f"Error deleting images for item {id}: {str(e)}")
    
    # Delete the item from the database
    if it.remove_item(id):
        flash(f'Item deleted successfully. Removed {stats["originals"]} images.', 'success')
    else:
        flash('Error deleting item from database.', 'error')
        
    return redirect(url_for('home_admin'))


@app.route('/edit_item/<id>', methods=['POST'])
def edit_item(id):
    """
    Route for editing an existing inventory item.
    
    Args:
        id (str): ID of the item to edit
        
    Returns:
        flask.Response: Redirect to admin homepage with status message
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    # Strip whitespace from all text fields
    name = strip_whitespace(request.form.get('name'))
    ort = strip_whitespace(request.form.get('ort'))
    beschreibung = strip_whitespace(request.form.get('beschreibung'))
    
    # Strip whitespace from all filter values
    filter1 = strip_whitespace(request.form.getlist('filter'))
    filter2 = strip_whitespace(request.form.getlist('filter2'))
    filter3 = strip_whitespace(request.form.getlist('filter3'))
    
    anschaffungs_jahr = strip_whitespace(request.form.get('anschaffungsjahr'))
    anschaffungs_kosten = strip_whitespace(request.form.get('anschaffungskosten'))
    code_4 = strip_whitespace(request.form.get('code_4'))
    
    # Check if code is unique (excluding the current item)
    if code_4 and not it.is_code_unique(code_4, exclude_id=id):
        flash('Der Code wird bereits verwendet. Bitte wählen Sie einen anderen Code.', 'error')
        return redirect(url_for('home_admin'))
    
    # Get current item to check availability status
    current_item = it.get_item(id)
    if not current_item:
        flash('Item not found', 'error')
        return redirect(url_for('home_admin'))
    
    # Preserve current availability status
    verfuegbar = current_item.get('Verfuegbar', True)
    
    # Handle existing images - get list of images to keep
    images_to_keep = request.form.getlist('existing_images')
    
    # Get the original list of images from the item
    original_images = current_item.get('Images', [])
    
    # Keep only the images that weren't marked for deletion
    images = [img for img in original_images if img in images_to_keep]
    
    # Handle new image uploads
    new_images = request.files.getlist('new_images')
    
    # Process any new image uploads
    for image in new_images:
        if image and image.filename:
            is_allowed, error_message = allowed_file(image.filename)
            if is_allowed:
                # Get the file extension
                _, ext_part = os.path.splitext(secure_filename(image.filename))
                
                # Generate a completely unique filename using UUID
                unique_id = str(uuid.uuid4())
                timestamp = time.strftime("%Y%m%d%H%M%S")
                
                # New filename format with UUID to ensure uniqueness
                filename = f"{unique_id}_{timestamp}{ext_part}"
                
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                images.append(filename)
            else:
                flash(error_message, 'error')
                return redirect(url_for('home_admin'))

    # If location is not in the predefined list, maybe add it (depending on policy)
    predefined_locations = it.get_predefined_locations()
    if ort and ort not in predefined_locations:
        it.add_predefined_location(ort)
    
    # Update the item
    result = it.update_item(
        id, name, ort, beschreibung, 
        images, verfuegbar, filter1, filter2, filter3,
        anschaffungs_jahr, anschaffungs_kosten, code_4
    )
    
    if result:
        flash('Item updated successfully', 'success')
    else:
        flash('Error updating item', 'error')
    
    return redirect(url_for('home_admin'))


@app.route('/get_ausleihungen', methods=['GET'])
def get_ausleihungen():
    """
    API endpoint to retrieve all borrowing records.
    
    Returns:
        dict: Dictionary containing all borrowing records
    """
    ausleihungen = au.get_ausleihungen()
    return {'ausleihungen': ausleihungen}


@app.route('/ausleihen/<id>', methods=['POST'])
def ausleihen(id):
    """
    Route for borrowing an item from inventory.
    
    Args:
        id (str): ID of the item to borrow
        
    Returns:
        flask.Response: Redirect to appropriate homepage
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    item = it.get_item(id)
    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('home'))
    
    # Before borrowing, block if there's a conflicting planned booking
    try:
        now = datetime.datetime.now()
        # Fetch planned bookings for this item from DB
        planned = au.get_planned_ausleihungen()
        # Count relevant upcoming planned bookings for today or ongoing
        upcoming_planned_today = []
        for appt in planned:
            appt_item = str(appt.get('Item')) if appt.get('Item') is not None else None
            if appt_item != id:
                continue
            appt_start = appt.get('Start')
            appt_end = appt.get('End') or appt_start
            if not appt_start:
                continue
            # Consider conflict if appointment ends in the future and is today
            try:
                if appt_end >= now and appt_start.date() == now.date():
                    upcoming_planned_today.append(appt)
            except Exception:
                # Fallback simple check
                if appt_start.date() == now.date():
                    upcoming_planned_today.append(appt)
        if upcoming_planned_today:
            # For single-instance items, block outright; for multi-exemplar, allow only if capacity suffices
            item_doc = it.get_item(id)
            total_exemplare = item_doc.get('Exemplare', 1) if item_doc else 1
            if total_exemplare <= 1:
                flash('Dieses Objekt hat heute eine geplante Reservierung und kann aktuell nicht ausgeliehen werden.', 'error')
                return redirect(url_for('home'))
            else:
                # If planned count equals or exceeds remaining capacity, block
                current_borrowed = len(item_doc.get('ExemplareStatus', [])) if item_doc else 0
                if current_borrowed + len(upcoming_planned_today) >= total_exemplare:
                    flash('Alle Exemplare sind aufgrund geplanter Reservierungen heute belegt.', 'error')
                    return redirect(url_for('home'))
    except Exception as e:
        print(f"Warning: could not enforce planned booking guard: {e}")

    # Get number of exemplars to borrow (default to 1)
    exemplare_count = request.form.get('exemplare_count', 1)
    try:
        exemplare_count = int(exemplare_count)
        if exemplare_count < 1:
            exemplare_count = 1
    except (ValueError, TypeError):
        exemplare_count = 1
        
    # Check if the item has exemplars defined
    total_exemplare = item.get('Exemplare', 1)
    
    # Get current exemplar status
    exemplare_status = item.get('ExemplareStatus', [])
    
    # Count how many exemplars are currently available
    borrowed_count = len(exemplare_status)
    available_count = total_exemplare - borrowed_count
    
    if available_count < exemplare_count:
        flash(f'Not enough copies available. Requested: {exemplare_count}, Available: {available_count}', 'error')
        return redirect(url_for('home'))
    
    # If we reach here, we can borrow the requested number of exemplars
    username = session['username']
    current_date = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    
    # If the item doesn't use exemplars (single item)
    if total_exemplare <= 1:
        it.update_item_status(id, False, username)
        start_date = datetime.datetime.now()
        au.add_ausleihung(id, username, start_date)
        flash('Item borrowed successfully', 'success')
    else:
        # Handle multi-exemplar item
        new_borrowed_exemplars = []
        
        # Create new entries for borrowed exemplars
        for i in range(exemplare_count):
            # Find the next available exemplar number
            exemplar_number = 1
            used_numbers = [ex.get('number') for ex in exemplare_status]
            
            while exemplar_number in used_numbers:
                exemplar_number += 1
                
            new_borrowed_exemplars.append({
                'number': exemplar_number,
                'user': username,
                'date': current_date
            })
        
        # Add new borrowed exemplars to the status
        updated_status = exemplare_status + new_borrowed_exemplars
        
        # Update the item with the new status
        it.update_item_exemplare_status(id, updated_status)
        
        # Update the item's availability if all exemplars are borrowed
        if len(updated_status) >= total_exemplare:
            it.update_item_status(id, False, username)
        
        # Create ausleihung records for each borrowed exemplar
        start_date = datetime.datetime.now()
        for exemplar in new_borrowed_exemplars:
            exemplar_id = f"{id}_{exemplar['number']}"
            au.add_ausleihung(exemplar_id, username, start_date, exemplar_data={
                'parent_id': id,
                'exemplar_number': exemplar['number']
            })
        
        flash(f'{exemplare_count} copies borrowed successfully', 'success')
    
    if 'username' in session and not us.check_admin(session['username']):
        return redirect(url_for('home'))
    return redirect(url_for('home_admin'))


@app.route('/zurueckgeben/<id>', methods=['POST'])
def zurueckgeben(id): 
    """
    Route for returning a borrowed item.
    Creates or updates a record of the borrowing session.
    
    Args:
        id (str): ID of the item to return
        
    Returns:
        flask.Response: Redirect to appropriate homepage
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    item = it.get_item(id)
    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('home'))
        
    username = session['username']
    
    print("Code 1169: zurueckgeben called with item ID:", id)

    if not item.get('Verfuegbar', True) and (us.check_admin(session['username']) or item.get('User') == username):
        print("Code 1172: Item is not available, proceeding with return")
        try:
            # Get ALL active borrowing records for this item and complete them
            client = MongoClient(MONGODB_HOST, MONGODB_PORT)
            db = client[MONGODB_DB]
            ausleihungen = db['ausleihungen']
            
            # Find all active records for this item
            active_records = ausleihungen.find({
                'Item': id,
                'Status': 'active'
            })
            
            end_date = datetime.datetime.now()
            original_user = item.get('User', username)
            
            updated_count = 0
            for record in active_records:
                ausleihung_id = str(record['_id'])
                print(f"Completing active ausleihung {ausleihung_id} for item {id}")
                
                # Update each active record
                result = ausleihungen.update_one(
                    {'_id': ObjectId(ausleihung_id)},
                    {'$set': {
                        'Status': 'completed',
                        'End': end_date,
                        'LastUpdated': datetime.datetime.now()
                    }}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
            
            client.close()
            
            # Update the item status
            it.update_item_status(id, True, original_user)
            
            if updated_count > 0:
                flash(f'Item returned successfully ({updated_count} record(s) completed)', 'success')
            else:
                flash('Item returned successfully', 'success')
                
        except Exception as e:
            print(f"Error in return process: {e}")
            it.update_item_status(id, True)
            flash(f'Item returned but encountered an error: {str(e)}', 'warning')
    else:
        flash('You are not authorized to return this item or it is already available', 'error')

    # Check if request came from my_borrowed_items page
    source_page = request.form.get('source_page')
    referrer = request.headers.get('Referer', '')
    if source_page == 'my_borrowed_items' or '/my_borrowed_items' in referrer:
        return redirect(url_for('my_borrowed_items'))
    
    if 'username' in session and not us.check_admin(session['username']):
        return redirect(url_for('home'))
    return redirect(url_for('home_admin'))

@app.route('/get_filter', methods=['GET'])
def get_filter():
    """
    API endpoint to retrieve available item filters/categories.
    
    Returns:
        dict: Dictionary of available filters
    """
    return it.get_filters()
    

@app.route('/get_ausleihung_by_item/<id>')
def get_ausleihung_by_item_route(id):
    """
    API endpoint to retrieve borrowing details for a specific item.
    
    Args:
        id (str): ID of the item to retrieve
        
    Returns:
        dict: Borrowing details for the item
    """
    if 'username' not in session:
        return {'error': 'Not authorized', 'status': 'forbidden'}, 403
    
    # Get the borrowing record
    ausleihung = au.get_ausleihung_by_item(id, include_history=False)        # Add client-side status verification if a borrowing record exists
    if ausleihung:
        # Add verified status to each borrowing record with logging
        current_status = au.get_current_status(
            ausleihung,
            log_changes=True, 
            user=session.get('username', None)
        )
        ausleihung['VerifiedStatus'] = current_status
    
    # Admin users can see all borrowing details
    # Regular users can only see their own borrowings
    if ausleihung and (us.check_admin(session['username']) or ausleihung.get('User') == session['username']):
        return {'ausleihung': ausleihung, 'status': 'success'}
    
    # Get item name for better error message
    item = it.get_item(id)
    item_name = item.get('Name', 'Unknown') if item else 'Unknown'
    
    # Return a more informative error
    return {
        'error': 'No active borrowing record found for this item',
        'item_name': item_name,
        'status': 'not_found'
    }, 200  # Return 200 instead of 404 to allow processing of the error message


@app.route('/get_planned_bookings/<item_id>')
def get_planned_bookings(item_id):
    """
    Return all planned bookings for a given item (admin only).
    """
    if 'username' not in session or not us.check_admin(session['username']):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    try:
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        ausleihungen = db['ausleihungen']
        cursor = ausleihungen.find({'Item': item_id, 'Status': 'planned'}).sort('Start', 1)
        bookings = []
        for r in cursor:
            bookings.append({
                'id': str(r.get('_id')),
                'user': r.get('User', ''),
                'period': r.get('Period'),
                'start': r.get('Start').isoformat() if r.get('Start') else None,
                'end': r.get('End').isoformat() if r.get('End') else None,
                'notes': r.get('Notes', '')
            })
        client.close()
        return jsonify({'ok': True, 'bookings': bookings})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/get_planned_bookings_public/<item_id>')
def get_planned_bookings_public(item_id):
    """
    Return planned bookings for a given item (normal users; limited fields, no notes).
    """
    if 'username' not in session:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    try:
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        ausleihungen = db['ausleihungen']
        cursor = ausleihungen.find({'Item': item_id, 'Status': 'planned'}).sort('Start', 1)
        bookings = []
        for r in cursor:
            bookings.append({
                'period': r.get('Period'),
                'start': r.get('Start').isoformat() if r.get('Start') else None,
                'end': r.get('End').isoformat() if r.get('End') else None
            })
        client.close()
        return jsonify({'ok': True, 'bookings': bookings})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/check_availability')
def check_availability():
    """
    Check if a given item is available for the specified date and period range.
    Query params: item_id, date=YYYY-MM-DD, start=<1-10>, end=<1-10>
    Returns: { ok, available, conflicts:[...] }
    """
    if 'username' not in session:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    item_id = request.args.get('item_id')
    date_str = request.args.get('date')
    start_p = request.args.get('start')
    end_p = request.args.get('end') or start_p
    if not item_id or not date_str or not start_p:
        return jsonify({'ok': False, 'error': 'missing parameters'}), 400

    try:
        # Parse date
        booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        start_num = int(start_p)
        end_num = int(end_p)
        if end_num < start_num:
            start_num, end_num = end_num, start_num

        # Compute requested time window
        start_times = get_period_times(booking_date, start_num)
        end_times = get_period_times(booking_date, end_num)
        if not start_times or not end_times:
            return jsonify({'ok': False, 'error': 'invalid period(s)'}), 400
        req_start = start_times['start']
        req_end = end_times['end']

        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        ausleihungen = db['ausleihungen']
        items_col = db['items']

        # Collect potential conflicts (planned and active) for this day
        same_day_start = datetime.datetime.combine(booking_date.date(), datetime.time.min)
        same_day_end = datetime.datetime.combine(booking_date.date(), datetime.time.max)
        candidates = list(ausleihungen.find({
            'Item': item_id,
            'Status': {'$in': ['planned', 'active']},
            'Start': {'$lte': same_day_end},
            'End': {'$gte': same_day_start}
        }))

        conflicts = []
        for r in candidates:
            r_start = r.get('Start')
            r_end = r.get('End')
            # If end missing for active, assume lasts through the day
            if r_end is None:
                r_end = same_day_end
            if r_start is None:
                r_start = same_day_start
            # Overlap check: req_start < r_end and req_end > r_start
            if req_start < r_end and req_end > r_start:
                conflicts.append({
                    'id': str(r.get('_id')),
                    'status': r.get('Status'),
                    'user': r.get('User', ''),
                    'start': r_start.isoformat() if r_start else None,
                    'end': r_end.isoformat() if r_end else None,
                    'period': r.get('Period')
                })

        # Also include current availability if checking today and item is borrowed now
        item_doc = items_col.find_one({'_id': ObjectId(item_id)})
        if item_doc and not item_doc.get('Verfuegbar', True):
            now = datetime.datetime.now()
            if req_start.date() == now.date():
                conflicts.append({'status': 'active', 'user': item_doc.get('User'), 'start': None, 'end': None, 'period': None, 'id': None})

        client.close()
        return jsonify({'ok': True, 'available': len(conflicts) == 0, 'conflicts': conflicts})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# def create_qr_code(id):
#     """
#     Generate a QR code for an item.
#     The QR code contains a URL that points to the item details.
#     
#     Args:
#         id (str): ID of the item to generate QR code for
#         
#     Returns:
#         str: Filename of the generated QR code, or None if item not found
#     """
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=ERROR_CORRECT_L,  # Use imported constant
#         box_size=10,
#         border=4,
#     )
#     
#     # Parse and reconstruct the URL properly
#     parsed_url = urlparse(request.url_root)
#     
#     # Force HTTPS if needed
#     scheme = 'https' if parsed_url.scheme == 'http' else parsed_url.scheme
#     
#     # Properly reconstruct the base URL
#     base_url = urlunparse((scheme, parsed_url.netloc, '', '', '', ''))
#     
#     # URL that will open this item directly
#     item_url = f"{base_url}:{Port}/item/{id}"
#     qr.add_data(item_url)
#     qr.make(fit=True)
#
#     item = it.get_item(id)
#     if not item:
#         return None
#     
#     img = qr.make_image(fill_color="black", back_color="white")
#     
#     # Create a unique filename using UUID
#     unique_id = str(uuid.uuid4())
#     timestamp = time.strftime("%Y%m%d%H%M%S")
#     
#     # Still include the original name for readability but ensure uniqueness with UUID
#     safe_name = secure_filename(item['Name'])
#     filename = f"{safe_name}_{unique_id}_{timestamp}.png"
#     qr_path = os.path.join(app.config['QR_CODE_FOLDER'], filename)
#
#     
#     # Fix the file handling - save to file object, not string
#     with open(qr_path, 'wb') as f:
#         img.save(f)
#     
#     return filename

# Fix fromisoformat None value checks
@app.route('/plan_booking', methods=['POST'])
def plan_booking():
    """
    Create a new planned booking or a range of bookings
    """
    if 'username' not in session:
        return {"success": False, "error": "Not authenticated"}, 401
        
    try:
        # Extract form data
        item_id = request.form.get('item_id')
        start_date_str = request.form.get('booking_date')  # Changed from start_date to booking_date
        end_date_str = request.form.get('booking_end_date')  # Changed from end_date to booking_end_date
        period_start = request.form.get('period_start')
        period_end = request.form.get('period_end')
        notes = request.form.get('notes', '')
        booking_type = request.form.get('booking_type', 'single')
        
        # Validate inputs
        if not all([item_id, start_date_str, end_date_str, period_start]):
            return {"success": False, "error": "Missing required fields"}, 400
            
        # Parse dates
        try:
            if start_date_str:
                start_date = datetime.datetime.fromisoformat(start_date_str)
            else:
                return {"success": False, "error": "Missing start date"}, 400
            
            if end_date_str:
                end_date = datetime.datetime.fromisoformat(end_date_str)
            else:
                return {"success": False, "error": "Missing end date"}, 400
            
            # For single day bookings, use the start date as the end date
            if booking_type == 'single':
                end_date = start_date
        except ValueError as e:
            return {"success": False, "error": f"Invalid date format: {e}"}, 400
            
        # Check if item exists
        item = it.get_item(item_id)
        if not item:
            return {"success": False, "error": "Item not found"}, 404
        
        # Handle period range
        periods = []
        if period_start:
            period_start_num = int(period_start)
        else:
            period_start_num = 1  # Default if None
    
        # If period_end is provided, it's a range of periods
        if period_end:
            period_end_num = int(period_end)
            
            # Validate period range
            if period_end_num < period_start_num:
                return {"success": False, "error": "End period cannot be before start period"}, 400
                
            # Create list of all periods in the range
            periods = list(range(period_start_num, period_end_num + 1))
        else:
            # Single period booking
            periods = [period_start_num]
            
        # For date range bookings, we'll process each date separately
        booking_ids = []
        errors = []
        
        # If it's a range of days
        if booking_type == 'range' and start_date != end_date:
            current_date = start_date
            while current_date <= end_date:
                # For each day in the range
                day_booking_ids, day_errors = process_day_bookings(
                    item_id, 
                    current_date,
                    periods,
                    notes
                )
                booking_ids.extend(day_booking_ids)
                errors.extend(day_errors)
                
                # Move to next day
                current_date += datetime.timedelta(days=1)
        else:
            # Single day with multiple periods
            booking_ids, errors = process_day_bookings(
                item_id,
                start_date,
                periods,
                notes
            )
            
        # Return results
        if errors:
            if booking_ids:
                # Some succeeded, some failed
                return {
                    "success": True, 
                    "partial": True,
                    "booking_ids": booking_ids,
                    "errors": errors
                }
            else:
                # All failed
                return {"success": False, "errors": errors}, 400
        else:
            # All succeeded
            return {"success": True, "booking_ids": booking_ids}
            
    except Exception as e:
        import traceback
        print(f"Error in plan_booking: {e}")
        traceback.print_exc()
        return {"success": False, "error": f"Server error: {str(e)}"}, 500

def process_day_bookings(item_id, booking_date, periods, notes):
    """
    Helper function to process bookings for a single day across multiple periods
    
    Args:
        item_id: The item to book
        booking_date: The date for the booking
        periods: List of period numbers to book
        notes: Booking notes
        
    Returns:
        tuple: (list of booking_ids, list of errors)
    """
    booking_ids = []
    errors = []
    
    for period in periods:
        # Get period times
        period_times = get_period_times(booking_date, period)
        if not period_times:
            errors.append(f"Invalid period {period}")
            continue
            
        # Create the start and end times for this period
        start_time = period_times.get('start')
        end_time = period_times.get('end')
        
        # Check for conflicts
        if au.check_booking_conflict(item_id, start_time, end_time, period):
            errors.append(f"Conflict for period {period} on {booking_date.strftime('%Y-%m-%d')}")
            continue
            
        # Create the booking
        booking_id = au.add_planned_booking(
            item_id,
            session['username'],
            start_time,
            end_time,
            notes,
            period=period
        )
        
        if booking_id:
            booking_ids.append(str(booking_id))
        else:
            errors.append(f"Failed to create booking for period {period}")
            
    return booking_ids, errors
@app.route('/add_booking', methods=['POST'])
def add_booking():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    item_id = request.form.get('item_id')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    period = request.form.get('period')
    notes = request.form.get('notes', '')
    
    # Parse dates as naive datetime objects
    try:
        # Simple datetime parsing without timezone
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d %H:%M:%S')
        else:
            return jsonify({'success': False, 'error': 'Missing start date'})
        
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d %H:%M:%S')
        else:
            end_date = None
        
        # Continue with adding the booking
        booking_id = au.add_planned_booking(
            item_id=item_id,
            user=session['username'],
            start_date=start_date,
            end_date=end_date,
            notes=notes,
            period=period
        )
        
        return jsonify({'success': True, 'booking_id': str(booking_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cancel_booking/<id>', methods=['POST'])
def cancel_booking(id):
    """
    Cancel a planned booking
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    # Get the booking
    booking = au.get_booking(id)
    if not booking:
        return {"success": False, "error": "Booking not found"}, 404
        
    # Check if user owns this booking
    if booking.get('User') != session['username'] and not us.check_admin(session['username']):
               return {"success": False, "error": "Not authorized to cancel this booking"}, 403
    
    # Cancel the booking
    result = au.cancel_booking(id)
    
    if result:
        return {"success": True}
    else:
        return {"success": False, "error": "Failed to cancel booking"}

@app.route('/terminplan', methods=['GET'])
def terminplan():
    """
    Route to display the booking calendar
    """
    try:
        if 'username' not in session:
            flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
            return redirect(url_for('login'))
        
        # Make sure the template exists
        template_path = os.path.join(BASE_DIR, 'templates', 'terminplan.html')
        if not os.path.exists(template_path):
            print(f"Template file not found: {template_path}")
            flash('Template not found. Please contact the administrator.', 'error')
            return redirect(url_for('home'))
            
        return render_template('terminplan.html', school_periods=SCHOOL_PERIODS)
    except Exception as e:
        import traceback
        print(f"Error rendering terminplan: {e}")
        traceback.print_exc()
        flash('An error occurred while displaying the calendar.', 'error')
        return redirect(url_for('home'))


'''-------------------------------------------------------------------------------------------------------------ADMIN ROUTES------------------------------------------------------------------------------------------------------------------'''

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration route.false
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if 'username' in session and us.check_admin(session['username']):
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            name = request.form['name']
            last_name = request.form['last-name']
            if not username or not password:
                flash('Please fill all fields', 'error')
                return redirect(url_for('register'))
            if us.get_user(username):
                flash('User already exists', 'error')
                return redirect(url_for('register'))
            if not us.check_password_strength(password):
                flash('Password is too weak', 'error')
                return redirect(url_for('register'))
            us.add_user(username, password, name, last_name)
            return redirect(url_for('home'))
        return render_template('register.html')
    flash('You are not authorized to view this page', 'error')
    return redirect(url_for('login'))


@app.route('/user_del', methods=['GET'])
def user_del():
    """
    User deletion interface.
    Displays a list of users that can be deleted by an administrator.
    Prevents self-deletion by hiding the current user from the list.
    
    Returns:
        flask.Response: Rendered template with user list or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    # Get all users except the current one (to prevent self-deletion)
    all_users = us.get_all_users()
    # Format them as needed for the template
    users_list = []
    for user in all_users:
        # Check different field names that might contain the username
        username = None
        for field in ['username']:
            if field in user:
                username = user[field]
                break
                
        # Only add if not the current user and we found a username
        if username and username != session['username']:
            try:
                fullname = us.get_full_name(username)
                name = fullname[0]
                last_name = fullname[1]
                fullname = f"{last_name} {name}"
            except:
                fullname = None
            users_list.append({
                'username': username,
                'admin': user.get('Admin', False),
                'fullname': fullname,
            })
    
    return render_template('user_del.html', users=users_list)


@app.route('/delete_user', methods=['POST'])
def delete_user():
    """
    Process user deletion request.
    Deletes a specified user from the system.
    Includes safety checks to prevent self-deletion.
    
    Returns:
        flask.Response: Redirect to the user deletion interface with status
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    username = request.form.get('username')
    if not username:
        flash('No user selected', 'error')
        return redirect(url_for('user_del'))
    
    # Prevent self-deletion
    if username == session['username']:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('user_del'))
    
    # Reset this user's borrowings and free items before deleting the user
    try:
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        ausleihungen = db['ausleihungen']
        items_col = db['items']
        now = datetime.datetime.now()

        # Complete all active borrowings of this user
        ausleihungen.update_many(
            {'User': username, 'Status': 'active'},
            {'$set': {'Status': 'completed', 'End': now, 'LastUpdated': now}}
        )

        # Cancel all planned borrowings of this user
        ausleihungen.update_many(
            {'User': username, 'Status': 'planned'},
            {'$set': {'Status': 'cancelled', 'LastUpdated': now}}
        )

        # Free all items currently associated with this user
        items_col.update_many(
            {'User': username},
            {'$set': {'Verfuegbar': True, 'LastUpdated': now}, '$unset': {'User': ""}}
        )

        client.close()
    except Exception as e:
        flash(f'Warnung: Ausleihungen/Reservierungen für {username} konnten nicht vollständig zurückgesetzt werden: {str(e)}', 'warning')

    # Delete the user
    try:
        us.delete_user(username)
        flash(f'User {username} deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('user_del'))


@app.route('/admin/borrowings')
def admin_borrowings():
    """
    Admin view: list all active and planned borrowings with ability to reset.
    """
    if 'username' not in session or not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))

    client = MongoClient(MONGODB_HOST, MONGODB_PORT)
    db = client[MONGODB_DB]
    ausleihungen = db['ausleihungen']
    items_col = db['items']

    # Load active and planned borrowings
    records = list(ausleihungen.find({'Status': {'$in': ['active', 'planned']}}).sort('Start', -1))

    def fmt_dt(dt):
        try:
            return dt.strftime('%d.%m.%Y %H:%M') if dt else ''
        except Exception:
            return str(dt) if dt else ''

    entries = []
    for r in records:
        print(r)
        it_id = r.get('Item')
        print(it_id)
        id = it.get_item(it_id)
        print(id)
        try:
            item_id = id.get('Code_4')
            item_name = id.get('Name')
        except:
            print(f"Failed to add: {r}")
            item_id = None
            print(f"Failed to add: {r}")
            item_name = None
        entries.append({
            'id': str(r.get('_id')),
            'item_id': str(item_id),
            'item_name': str(item_name),
            'user': r.get('User', ''),
            'status': r.get('Status', ''),
            'start': fmt_dt(r.get('Start')),
            'end': fmt_dt(r.get('End')),
            'period': r.get('Period') if r.get('Period') is not None else '',
            'notes': r.get('Notes', '')
        })

    client.close()

    return render_template('admin_borrowings.html', entries=entries)


@app.route('/admin/reset_borrowing/<borrow_id>', methods=['POST'])
def admin_reset_borrowing(borrow_id):
    """
    Admin action: reset a single borrowing.
    - If active: complete it and free the item
    - If planned: cancel it
    """
    if 'username' not in session or not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))

    try:
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        ausleihungen = db['ausleihungen']
        items_col = db['items']

        rec = ausleihungen.find_one({'_id': ObjectId(borrow_id)})
        if not rec:
            client.close()
            flash('Ausleihung nicht gefunden', 'error')
            return redirect(url_for('admin_borrowings'))

        status = rec.get('Status')
        item_id = rec.get('Item')
        user = rec.get('User')

        now = datetime.datetime.now()
        if status == 'active':
            ausleihungen.update_one({'_id': rec['_id']}, {'$set': {'Status': 'completed', 'End': now, 'LastUpdated': now}})
            # Free the item
            if item_id:
                try:
                    items_col.update_one({'_id': ObjectId(item_id)}, {'$set': {'Verfuegbar': True, 'LastUpdated': now}, '$unset': {'User': ""}})
                except Exception:
                    pass
            flash('Aktive Ausleihe wurde zurückgesetzt (abgeschlossen).', 'success')
        elif status == 'planned':
            ausleihungen.update_one({'_id': rec['_id']}, {'$set': {'Status': 'cancelled', 'LastUpdated': now}})
            flash('Geplante Ausleihe wurde storniert.', 'success')
        else:
            flash('Diese Ausleihe ist weder aktiv noch geplant.', 'warning')

        client.close()
    except Exception as e:
        flash(f'Fehler beim Zurücksetzen: {str(e)}', 'error')

    return redirect(url_for('admin_borrowings'))


@app.route('/admin_reset_user_password', methods=['POST'])
def admin_reset_user_password():
    """
    Admin route to reset a user's password.
    Resets the password for the specified user to a temporary password.
    Only accessible by administrators.
    
    Returns:
        flask.Response: Redirect to user management page with status message
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adresse zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
        
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adresse zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    username = request.form.get('username')
    new_password = request.form.get('new_password', 'Password123')  # Default temporary password
    
    if not username:
        flash('Kein Benutzer ausgewählt', 'error')
        return redirect(url_for('user_del'))
    
    # Check if user exists
    user = us.get_user(username)
    if not user:
        flash(f'Benutzer {username} nicht gefunden', 'error')
        return redirect(url_for('user_del'))
    
    # Prevent changing own password through this route (use change_password instead)
    if username == session['username']:
        flash('Sie können Ihr eigenes Passwort nicht über diese Funktion ändern. Bitte verwenden Sie dafür die Option "Passwort ändern" im Profil-Menü.', 'error')
        return redirect(url_for('user_del'))
    
    # Reset the password
    try:
        us.update_password(username, new_password)
        flash(f'Passwort für {username} wurde erfolgreich zurückgesetzt auf: {new_password}', 'success')
    except Exception as e:
        flash(f'Fehler beim Zurücksetzen des Passworts: {str(e)}', 'error')
    
    return redirect(url_for('user_del'))


@app.route('/logs')
def logs():
    """
    View system logs interface.
    Displays a history of all item borrowings with detailed information.
    
    Returns:
        flask.Response: Rendered template with logs or redirect if not authenticated
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
        
    # Get ausleihungen
    all_ausleihungen = au.get_ausleihungen()
    
    formatted_items = []
    for ausleihung in all_ausleihungen:
        try:
            # Get item details - from sample data, Item is an ID
            item = it.get_item(ausleihung.get('Item'))
            item_name = item.get('Name', 'Unknown Item') if item else 'Unknown Item'
            
            # Get user details - from sample data, User is a username string
           

            username = ausleihung.get('User', 'Unknown User')
            # Determine (verified) status for display
            try:
                display_status = au.get_current_status(ausleihung)
            except Exception:
                display_status = ausleihung.get('Status', 'unknown')
            
            # Format dates for display
            start_date = ausleihung.get('Start')
            if isinstance(start_date, datetime.datetime):
                start_date = start_date.strftime('%Y-%m-%d %H:%M')
                
            end_date = ausleihung.get('End', 'Not returned')
            if isinstance(end_date, datetime.datetime):
                end_date = end_date.strftime('%Y-%m-%d %H:%M')
            
            # Calculate duration
            duration = 'N/A'
            if isinstance(ausleihung.get('Start'), datetime.datetime) and isinstance(ausleihung.get('End'), datetime.datetime):
                duration_td = ausleihung['End'] - ausleihung['Start']
                hours, remainder = divmod(duration_td.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if duration_td.days > 0:
                    duration = f"{duration_td.days}d {hours}h {minutes}m"
                else:
                    duration = f"{hours}h {minutes}m"
            
            formatted_items.append({
                'Item': item_name,
                'User': username,
                'Start': start_date,
                'End': end_date,
                'Duration': duration,
                'Status': display_status,
                'id': str(ausleihung['_id'])
            })
        except Exception as e:
            continue
    
    return render_template('logs.html', items=formatted_items)


@app.route('/get_logs', methods=['GET'])
def get_logs():
    """
    API endpoint to retrieve all borrowing logs.
    
    Returns:
        dict: Dictionary containing all borrowing records or redirect if not authenticated
    """
    if not session.get('username'):
        return redirect(url_for('login'))
    logs = au.get_ausleihungen()
    return logs


@app.route('/get_usernames', methods=['GET'])
def get_usernames():
    """
    API endpoint to retrieve all usernames from the system.
    Requires administrator privileges.
    
    Returns:
        dict: Dictionary containing all users or redirect if not authenticated
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('logout'))
    elif 'username' in session and us.check_admin(session['username']):
        return jsonify(us.get_all_users())  # Fixed to use get_all_users
    else:
        flash('Please login to access this function', 'error')
        return redirect(url_for('login'))  # Added proper return

# New routes for filter management

@app.route('/manage_filters')
def manage_filters():
    """
"
    Admin page to manage predefined filter values.
    
    Returns:
        flask.Response: Rendered filter management template or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    # Get predefined filter values
    filter1_values = it.get_predefined_filter_values(1)
    filter2_values = it.get_predefined_filter_values(2)
    
    return render_template('manage_filters.html', 
                          filter1_values=filter1_values, 
                          filter2_values=filter2_values)

@app.route('/add_filter_value/<int:filter_num>', methods=['POST'])
def add_filter_value(filter_num):
    """
    Add a new predefined value to the specified filter.
    
    Args:
        filter_num (int): Filter number (1 or 2)
        
    Returns:
        flask.Response: Redirect to filter management page
    """
    if 'username' not in session or not us.check_admin(session['username']):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    value = strip_whitespace(request.form.get('value'))
    
    if not value:
        flash('Bitte geben Sie einen Wert ein', 'error')
        return redirect(url_for('manage_filters'))
    
    # Add the value to the filter
    success = it.add_predefined_filter_value(filter_num, value)
    
    if success:
        flash(f'Wert "{value}" wurde zu Filter {filter_num} hinzugefügt', 'success')
    else:
        flash(f'Wert "{value}" existiert bereits in Filter {filter_num}', 'error')
    
    return redirect(url_for('manage_filters'))

@app.route('/remove_filter_value/<int:filter_num>/<string:value>', methods=['POST'])
def remove_filter_value(filter_num, value):
    """
    Remove a predefined value from the specified filter.
    
    Args:
        filter_num (int): Filter number (1 or 2)
        value (str): Value to remove
        
    Returns:
        flask.Response: Redirect to filter management page
    """
    if 'username' not in session or not us.check_admin(session['username']):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    # Remove the value from the filter
    success = it.remove_predefined_filter_value(filter_num, value)
    
    if success:
        flash(f'Wert "{value}" wurde aus Filter {filter_num} entfernt', 'success')
    else:
        flash(f'Fehler beim Entfernen des Wertes "{value}" aus Filter {filter_num}', 'error')
    
    return redirect(url_for('manage_filters'))

@app.route('/get_predefined_filter_values/<int:filter_num>')
def get_predefined_filter_values(filter_num):
    """
    API endpoint to get predefined values for a specific filter.
    
    Args:
        filter_num (int): Filter number (1 or 2)

        
    Returns:
        dict: Dictionary containing predefined filter values
    """
    values = it.get_predefined_filter_values(filter_num)
    return jsonify({'values': values})

@app.route('/search_word/<path:word>')
def search_word(word):
    """Search items by Titel (Name) and Beschreibung, case-insensitive.

    Returns: JSON with list of matching item IDs.
    """
    try:
        term = (word or "").strip()
        if not term:
            return jsonify({"success": True, "response": []})

        term_lower = term.lower()
        id_set = set()
        for i in it.get_items():
            beschreibung = i.get("Beschreibung", "")
            titel = i.get("Name", "")
            # Normalize Beschreibung to string
            try:
                if isinstance(beschreibung, (list, tuple)):
                    text = " ".join([str(x) for x in beschreibung])
                else:
                    text = str(beschreibung)
            except Exception:
                text = ""

            # Normalize title
            try:
                title_text = str(titel)
            except Exception:
                title_text = ""

            if (term_lower in text.lower()) or (term_lower in title_text.lower()):
                _id = i.get("_id")
                if _id is not None:
                    id_set.add(str(_id))

        return jsonify({"success": True, "response": list(id_set)})
    except Exception as e:
        return jsonify({"success": False, "response": str(e)})

@app.route('/fetch_book_info/<isbn>')
def fetch_book_info(isbn):
    """
    API endpoint to fetch book information by ISBN using Google Books API
    
    Args:
        isbn (str): ISBN to look up
        
    Returns:
        dict: Book information or error message
    """
    try:
        # Clean the ISBN (remove hyphens and spaces)
        clean_isbn = isbn.replace('-', '').replace(' ', '')
        
        # Query the Google Books API
        response = requests.get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}")
        
        # Check if the request was successful
        if response.status_code != 200:
            return jsonify({"error": f"API request failed with status code: {response.status_code}"}), 500
        
        # Parse the response
        data = response.json()
        
        # Check if books were found
        if data.get('totalItems', 0) == 0:
            return jsonify({"error": f"No books found for ISBN: {isbn}"}), 404
        
        # Get the first book's information
        book_info = data['items'][0]['volumeInfo']
        sale_info = data['items'][0].get('saleInfo', {})
        
        # Extract price information if available
        price = None
        retail_price = sale_info.get('retailPrice', {})
        list_price = sale_info.get('listPrice', {})
        
        if retail_price and 'amount' in retail_price:
            price = f"{retail_price['amount']} {retail_price.get('currencyCode', '€')}"
        elif list_price and 'amount' in list_price:
            price = f"{list_price['amount']} {list_price.get('currencyCode', '€')}"
        
        # Extract relevant information
        result = {
            "title": book_info.get('title', 'Unknown Title'),
            "authors": ', '.join(book_info.get('authors', ['Unknown Author'])),
            "publisher": book_info.get('publisher', 'Unknown Publisher'),
            "publishedDate": book_info.get('publishedDate', 'Unknown Date'),
            "description": book_info.get('description', 'No description available'),
            "pageCount": book_info.get('pageCount', 'Unknown'),
            "price": price
        }
        
        # Ensure thumbnail URL uses HTTPS
        thumbnail = book_info.get('imageLinks', {}).get('thumbnail', '')
        if thumbnail:
            thumbnail = thumbnail.replace('http:', 'https:')
        result["thumbnail"] = thumbnail
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error fetching book data: {e}")
        return jsonify({"error": f"Failed to fetch book information: {str(e)}"}), 500

@app.route('/download_book_cover', methods=['POST'])
def download_book_cover():
    """
    API endpoint to download and save a book cover image from URL
    
    Returns:
        dict: Success status and filename or error message
    """
    if 'username' not in session:
        return jsonify({"error": "Not authorized"}), 403
    if not us.check_admin(session['username']):
        return jsonify({"error": "Admin privileges required"}), 403
    
    try:
        data = request.get_json()
        image_url = data.get('url')
        
        if not image_url:
            return jsonify({"error": "No image URL provided"}), 400
        
        # Download the image
        response = requests.get(image_url, stream=True, timeout=10)
        
        if response.status_code != 200:
            return jsonify({"error": f"Failed to download image: Status {response.status_code}"}), 400
        
        # Check content type to ensure it's an image of allowed format
        content_type = response.headers.get('content-type', '')
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
        
        if not any(allowed_type in content_type.lower() for allowed_type in allowed_types):
            return jsonify({
                "error": f"Nicht unterstütztes Bildformat: {content_type}. Erlaubte Formate: JPG, JPEG, PNG, GIF"
            }), 400
        
        # Generate a fully unique filename using UUID
        import uuid
        import time
        
        unique_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y%m%d%H%M%S")
        
        # Use appropriate extension based on content type
        extension = '.jpg'  # default
        if 'image/png' in content_type.lower():
            extension = '.png'
        elif 'image/gif' in content_type.lower():
            extension = '.gif'
            
        filename = f"book_cover_{unique_id}_{timestamp}{extension}"
        
        # Save the image to uploads folder
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return jsonify({
            "success": True,
            "filename": filename,
            "message": "Image downloaded successfully"
        })
        
    except Exception as e:
        print(f"Error downloading book cover: {e}")
       
        return jsonify({"error": f"Failed to download image: {str(e)}"}), 500

@app.route('/proxy_image')
def proxy_image():
    """
    Proxy endpoint to fetch images from external sources,
    bypassing CORS restrictions
    
    Returns:
        flask.Response: The image data or an error response
    """
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    try:
        # Fetch the image from the external source
        response = requests.get(url, stream=True, timeout=5)
        
        # Check if the request was successful
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch image: Status {response.status_code}"}), response.status_code
        
        # Get the content type
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # Return the image data with appropriate headers
        return Response(
            response=response.content,
            status=200,
            headers={
                'Content-Type': content_type
            }
        )
    except Exception as e:
        print(f"Error in proxy_image: {e}")
        return jsonify({"error": f"Error fetching image: {str(e)}"}), 500

# Add missing get_period_times function
def get_period_times(booking_date, period_num):
    """
    Get the start and end times for a given period on a specific date
    
    Args:
        booking_date (datetime): The date for the booking
        period_num (int): The period number
    
    Returns:
        dict: {"start": datetime, "end": datetime} or None if invalid
    """
    try:
        # Convert period_num to string for lookup in SCHOOL_PERIODS
        period_str = str(period_num)
        
        if period_str not in SCHOOL_PERIODS:
            return None
            
        period_info = SCHOOL_PERIODS[period_str]
        
        # Extract start and end times from period info
        start_time_str = period_info.get('start')
        end_time_str = period_info.get('end')
        
        if not start_time_str or not end_time_str:
            return None
            
        # Parse hours and minutes
        start_hour, start_min = map(int, start_time_str.split(':'))
        end_hour, end_min = map(int, end_time_str.split(':'))
        
        # Create datetime objects for start and end times
        start_datetime = datetime.datetime.combine(
            booking_date.date(),
            datetime.time(start_hour, start_min)
        )
        
        end_datetime = datetime.datetime.combine(
            booking_date.date(),
            datetime.time(end_hour, end_min)
        )
        
        return {
            'start': start_datetime,
            'end': end_datetime
        }
    except Exception as e:
        print(f"Error getting period times: {e}")
        return None

@app.route('/my_borrowed_items')
def my_borrowed_items():
    """
    Zeigt alle vom aktuellen Benutzer ausgeliehenen und geplanten Objekte an.
    
    Returns:
        Response: Gerendertes Template mit den ausgeliehenen und geplanten Objekten des Benutzers
    """
    if 'username' not in session:
        flash('Bitte melden Sie sich an, um Ihre ausgeliehenen Objekte anzuzeigen', 'error')
        return redirect(url_for('login', next=request.path))
    
    username = session['username']
    client = MongoClient(MONGODB_HOST, MONGODB_PORT)
    db = client[MONGODB_DB]
    items_collection = db.items
    ausleihungen_collection = db.ausleihungen
    
    # Get current time for comparison
    current_time = datetime.datetime.now()
    
    # Check if user is admin
    user_is_admin = False
    if 'is_admin' in session:
        user_is_admin = session['is_admin']
    
    # Get items currently borrowed by the user (where Verfuegbar=false and User=username)
    borrowed_items = list(items_collection.find({'Verfuegbar': False, 'User': username}))
    
    # Get active and planned ausleihungen for the user
    active_ausleihungen = list(ausleihungen_collection.find({
        'User': username,
        'Status': 'active'
    }))
    
    planned_ausleihungen = list(ausleihungen_collection.find({
        'User': username,
        'Status': 'planned',
        'Start': {'$gt': current_time}
    }))
    
    # DEBUG: Log the number of planned appointments found
    app.logger.info(f"Found {len(planned_ausleihungen)} planned appointments for user {username}")
    for appt in planned_ausleihungen:
        app.logger.info(f"Planned appointment: ID={str(appt['_id'])}, Item={str(appt.get('Item'))}, Start={appt.get('Start')}")
    
    # Process items
    active_items = []
    planned_items = []
    processed_item_ids = set()  # Keep track of processed item IDs to avoid duplicates
    
    # First, process items that are directly marked as borrowed by the user
    for item in borrowed_items:
        # Convert ObjectId to string for template
        item['_id'] = str(item['_id'])
        active_items.append(item)
        processed_item_ids.add(item['_id'])
    
    # Process active appointments
    for appointment in active_ausleihungen:
        # Get the item ID from the appointment
        item_id = appointment.get('Item')
        
        if not item_id or str(item_id) in processed_item_ids:
            continue  # Skip if we already processed this item or no item ID
        
        # Get item details
        item_obj = items_collection.find_one({'_id': ObjectId(item_id)})
        
        if item_obj:
            # Convert ObjectId to string for template
            item_obj['_id'] = str(item_obj['_id'])
            
            # Add appointment data
            item_obj['AppointmentData'] = {
                'id': str(appointment['_id']),
                'start': appointment.get('Start'),
                'end': appointment.get('End'),
                'notes': appointment.get('Notes'),
                'period': appointment.get('Period'),
                'status': appointment.get('VerifiedStatus', appointment.get('Status')),
            }
            
            # Mark that this item is part of an active appointment
            item_obj['ActiveAppointment'] = True
            
            # Add to the list only if not already there
            if str(item_obj['_id']) not in processed_item_ids:
                active_items.append(item_obj)
                processed_item_ids.add(str(item_obj['_id']))
    
    # Process planned appointments
    for appointment in planned_ausleihungen:
        item_id = appointment.get('Item')
        
        if not item_id:
            continue
        
        item_obj = items_collection.find_one({'_id': ObjectId(item_id)})
        
        if item_obj:
            item_obj['_id'] = str(item_obj['_id'])
            
            # Add appointment data
            item_obj['AppointmentData'] = {
                'id': str(appointment['_id']),
                'start': appointment.get('Start'),
                'end': appointment.get('End'),
                'notes': appointment.get('Notes'),
                'period': appointment.get('Period'),
                'status': appointment.get('Status'),
            }
            
            planned_items.append(item_obj)
    
    client.close()
    
    # DEBUG: Log what we're passing to the template
    app.logger.info(f"Passing {len(active_items)} active items and {len(planned_items)} planned items to template")
    if planned_items:
        for i, item in enumerate(planned_items):
            app.logger.info(f"Planned item {i+1}: {item['Name']}, Appointment ID: {item['AppointmentData']['id']}")
    
    return render_template(
        'my_borrowed_items.html',
        items=active_items,
        planned_items=planned_items,
        user_is_admin=user_is_admin
    )

@app.route('/favicon.ico')
def favicon():
    """
    Serve the favicon directly from the static directory.
    
    Returns:
        flask.Response: The favicon.ico file
    """
    return send_from_directory(app.static_folder, 'favicon.ico')

@app.route('/get_predefined_locations')
def get_predefined_locations_route():
    """
    API endpoint to get predefined locations.
    
    Returns:
        dict: Dictionary containing predefined location values
    """
    values = it.get_predefined_locations()
    return jsonify({'locations': values})

@app.route('/add_location_value', methods=['POST'])
def add_location_value():
    """
    Add a new predefined location value.
    
    Returns:
        flask.Response: Redirect to location management page
    """
    if 'username' not in session or not us.check_admin(session['username']):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    value = strip_whitespace(request.form.get('value'))
    
    if not value:
        flash('Bitte geben Sie einen Wert ein', 'error')
        return redirect(url_for('manage_locations'))
    
    # Add the value to locations
    success = it.add_predefined_location(value)
    
    if success:
        flash(f'Ort "{value}" wurde zur Liste hinzugefügt', 'success')
    else:
        flash(f'Ort "{value}" existiert bereits', 'error')
    
    return redirect(url_for('manage_locations'))

@app.route('/remove_location_value/<string:value>', methods=['POST'])
def remove_location_value(value):
    """
    Remove a predefined location value.
    
    Args:
        value (str): Value to remove
        
    Returns:
        flask.Response: Redirect to location management page
    """
    if 'username' not in session or not us.check_admin(session['username']):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    # Remove the value from locations
    success = it.remove_predefined_location(value)
    
    if success:
        flash(f'Ort "{value}" wurde aus der Liste entfernt', 'success')
    else:
        flash(f'Fehler beim Entfernen des Ortes "{value}"', 'error')
    
    return redirect(url_for('manage_locations'))

@app.route('/manage_locations')
def manage_locations():
    """
    Admin page to manage predefined location values.
    
    Returns:
        flask.Response: Rendered location management template or redirect
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    # Get predefined location values
    location_values = it.get_predefined_locations()
    
    return render_template('manage_locations.html', 
                          location_values=location_values)

@app.route('/check_code_unique/<code>')
def check_code_unique(code):
    """
    API endpoint to check if a code is unique
    
    Args:
        code (str): Code to check
        exclude_id (str, optional): ID of item to exclude from check (for edit operations)
        
    Returns:
        dict: JSON response with is_unique boolean
    """
    exclude_id = request.args.get('exclude_id')
    is_unique = it.is_code_unique(code, exclude_id)
    
    return jsonify({
        'is_unique': is_unique,
        'code': code
    })

@app.route('/schedule_appointment', methods=['POST'])
def schedule_appointment():
    """
    Schedule an appointment for an item
    """
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        # Extract form data
        item_id = request.form.get('item_id')
        schedule_date = request.form.get('schedule_date')
        start_period = request.form.get('start_period')
        end_period = request.form.get('end_period')
        notes = request.form.get('notes', '')
        
        # Validate inputs
        if not all([item_id, schedule_date, start_period, end_period]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        # Parse the date
        try:
            appointment_date_obj = datetime.datetime.strptime(schedule_date, '%Y-%m-%d')
            appointment_date = appointment_date_obj.date()  # Get date part only
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400
            
        # Validate periods
        try:
            start_period_num = int(start_period)
            end_period_num = int(end_period)
            
            if start_period_num > end_period_num:
                return jsonify({'success': False, 'message': 'Start period cannot be after end period'}), 400
                
            if not (1 <= start_period_num <= 10) or not (1 <= end_period_num <= 10):
                return jsonify({'success': False, 'message': 'Invalid period numbers'}), 400
                
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid period values'}), 400
            
        # Check if item exists
        item = it.get_item(item_id)
        if not item:
            return jsonify({'success': False, 'message': 'Item not found'}), 404
            
        # Calculate start and end times for the appointment
        # Make sure we're passing the correct datetime object
        period_start_datetime = datetime.datetime.combine(appointment_date, datetime.time())
        period_times_start = get_period_times(period_start_datetime, start_period_num)
        period_times_end = get_period_times(period_start_datetime, end_period_num)
        
        # Check if we got valid period times
        if not period_times_start or not period_times_end:
            print(f"Invalid period times: start={period_times_start}, end={period_times_end}")
            return jsonify({'success': False, 'message': 'Invalid period times'}), 400
            
        start_datetime = period_times_start['start']
        end_datetime = period_times_end['end']
        
        # Check for conflicts (use full period-range aware check)
        try:
            has_conflict = au.check_booking_period_range_conflict(
                item_id,
                start_datetime,
                end_datetime,
                period=start_period_num,
                period_end=end_period_num
            )
            if has_conflict:
                return jsonify({'success': False, 'message': 'Appointment conflicts with existing booking'}), 409
        except Exception as e:
            print(f"Error checking for booking conflicts: {e}")
            return jsonify({'success': False, 'message': f'Error checking availability: {str(e)}'}), 500
            
        # Create the appointment as a planned booking
        try:
            appointment_id = au.add_planned_booking(
                item_id=item_id,
                user=session['username'],
                start_date=start_datetime,
                end_date=end_datetime,
                notes=notes,
                period=start_period_num
            )
            
            if not appointment_id:
                return jsonify({'success': False, 'message': 'Failed to create appointment'}), 500
        except Exception as e:
            print(f"Error creating planned booking: {e}")
            return jsonify({'success': False, 'message': f'Error creating appointment: {str(e)}'}), 500
        
        # If we got this far, we have a valid appointment_id
        try:
            # Update item with next scheduled appointment info
            # Convert date to datetime for MongoDB storage if needed
            if isinstance(appointment_date, datetime.date) and not isinstance(appointment_date, datetime.datetime):
                appointment_datetime = datetime.datetime.combine(appointment_date, datetime.time())
            else:
                appointment_datetime = appointment_date
                
            result = it.update_item_next_appointment(item_id, {
                'date': appointment_datetime,
                'start_period': start_period_num,
                'end_period': end_period_num,
                'user': session['username'],
                'notes': notes,
                'appointment_id': str(appointment_id)
            })
            
            if result:
                return jsonify({'success': True, 'appointment_id': str(appointment_id)})
            else:
                print("Failed to update item with appointment info")
                return jsonify({'success': False, 'message': 'Failed to update item with appointment info'}), 500
                
        except Exception as e:
            print(f"Error updating item with appointment info: {e}")
            return jsonify({'success': False, 'message': f'Error updating item: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Error creating appointment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error occurred: {str(e)}'}), 500

@app.route('/cancel_ausleihung/<id>', methods=['POST'])
def cancel_ausleihung_route(id):
    """
    Route for canceling a planned or active ausleihung.
    
    Args:
        id (str): ID of the ausleihung to cancel
        
    Returns:
        flask.Response: Redirect to My Ausleihungen page
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
        
    username = session['username']
    
    try:
        print(f"Attempting to cancel ausleihung with ID: {id}")
        
        # Get the ausleihung record to check if it belongs to the current user
        ausleihung = au.get_ausleihung(id)
        
        if not ausleihung:
            print(f"Ausleihung not found with ID: {id}")
            flash('Ausleihung nicht gefunden', 'error')
            return redirect(url_for('my_borrowed_items'))
            
        # Log ausleihung details for debugging
        ausleihung_status = ausleihung.get('Status', 'unknown')
        ausleihung_user = ausleihung.get('User', 'unknown')
        print(f"Found ausleihung: ID={id}, User={ausleihung_user}, Status={ausleihung_status}")
            
        # Check if the ausleihung belongs to the current user
        if ausleihung_user != username and not us.check_admin(username):
            print(f"Authorization failure: {username} attempted to cancel ausleihung belonging to {ausleihung_user}")
            flash('Sie sind nicht berechtigt, diese Ausleihung zu stornieren', 'error')
            return redirect(url_for('my_borrowed_items'))
            
        # Cancel the ausleihung
        if au.cancel_ausleihung(id):
            print(f"Successfully canceled ausleihung with ID: {id}")
            flash('Ausleihung wurde erfolgreich storniert', 'success')
            # Also clear NextAppointment on the related item if it matches this appointment
            try:
                item_id = str(ausleihung.get('Item')) if ausleihung.get('Item') is not None else None
                if item_id:
                    item_doc = it.get_item(item_id)
                    if item_doc:
                        next_appt = item_doc.get('NextAppointment', {})
                        if next_appt and str(next_appt.get('appointment_id')) == str(id):
                            cleared = it.clear_item_next_appointment(item_id)
                            print(f"Cleared NextAppointment for item {item_id}: {cleared}")
            except Exception as clear_err:
                print(f"Warning: could not clear NextAppointment for cancelled ausleihung {id}: {clear_err}")
        else:
            print(f"Failed to cancel ausleihung with ID: {id}")
            flash('Fehler beim Stornieren der Ausleihung', 'error')
            
    except Exception as e:
        print(f"Error canceling ausleihung: {e}")
        flash(f'Fehler: {str(e)}', 'error')
        
    return redirect(url_for('my_borrowed_items'))

@app.route('/reset_item/<id>', methods=['POST'])
def reset_item(id):
    """
    Route for completely resetting an item's borrowing status.
    This handles items that have inconsistent borrowing states.
    
    Args:
        id (str): ID of the item to reset
        
    Returns:
        JSON: Success status and details
    """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if not us.check_admin(session['username']):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    try:
        # Import the ausleihung module
        import ausleihung as au
        
        result = au.reset_item_completely(id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'details': result.get('details', {})
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400
            
    except Exception as e:
        print(f"Error in reset_item route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# New image and video optimization functions
def is_image_file(filename):
    """
    Check if a file is an image based on its extension.
    
    Args:
        filename (str): Name of the file to check
        
    Returns:
        bool: True if the file is an image, False otherwise
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg'}
    extension = filename.lower()[filename.rfind('.'):]
    return extension in image_extensions


def is_video_file(filename):
    """
    Check if a file is a video based on its extension.
    
    Args:
        filename (str): Name of the file to check
        
    Returns:
        bool: True if the file is a video, False otherwise
    """
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v', '.3gp'}
    extension = filename.lower()[filename.rfind('.'):]
    return extension in video_extensions


def create_image_thumbnail(image_path, thumbnail_path, size, debug_prefix=""):
    """
    Create a thumbnail for an image file, always converting to JPG format.
    
    Args:
        image_path (str): Path to the original image
        thumbnail_path (str): Path where the thumbnail should be saved
        size (tuple): Thumbnail size as (width, height)
        debug_prefix (str, optional): Prefix for debug logs
        
    Returns:
        bool: True if thumbnail was created successfully, False otherwise
    """
    # Check if this is a PNG file
    is_png = image_path.lower().endswith('.png')
    log_prefix = debug_prefix if debug_prefix else (f"PNG DEBUG: [{os.path.basename(image_path)}]" if is_png else "")
    
    try:
        if is_png and log_prefix:
            app.logger.info(f"{log_prefix} Creating thumbnail from PNG: {image_path} -> {thumbnail_path}")
            # Check the PNG file header directly
            try:
                with open(image_path, 'rb') as f:
                    header_bytes = f.read(16)
                    png_signature = b'\x89PNG\r\n\x1a\n'
                    is_valid_signature = header_bytes.startswith(png_signature)
                    header_hex = ' '.join([f"{b:02x}" for b in header_bytes[:16]])
                    app.logger.info(f"{log_prefix} PNG file header: {header_hex}")
                    app.logger.info(f"{log_prefix} PNG has valid signature: {is_valid_signature}")
            except Exception as header_err:
                app.logger.error(f"{log_prefix} Error checking PNG header: {str(header_err)}")
            
        try:
            with Image.open(image_path) as img:
                if is_png and log_prefix:
                    app.logger.info(f"{log_prefix} PNG opened successfully: Format={img.format}, Mode={img.mode}, Size={img.size}")
                    app.logger.info(f"{log_prefix} PNG bands: {img.getbands()}")
                
                # Always convert to RGB for JPG output
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create a white background
                    if is_png and log_prefix:
                        app.logger.info(f"{log_prefix} Converting PNG from {img.mode} to RGB with background")
                        
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        if is_png and log_prefix:
                            app.logger.info(f"{log_prefix} Converting PNG from P to RGBA first")
                            # Check if palette has transparency
                            has_transparency = img.info.get('transparency') is not None
                            app.logger.info(f"{log_prefix} PNG palette has transparency: {has_transparency}")
                        img = img.convert('RGBA')
                    
                    # For PNG files, let's add extra transparency debug
                    if is_png and log_prefix:
                        if img.mode == 'RGBA':
                            # Check if image actually has transparency
                            alpha = img.split()[3]
                            has_transparency = alpha.getextrema()[0] < 255
                            app.logger.info(f"{log_prefix} PNG has transparency: {has_transparency}")
                            
                    # Do the paste with alpha mask if available
                    if img.mode == 'RGBA':
                        alpha_channel = img.split()[3]
                        if is_png and log_prefix:
                            app.logger.info(f"{log_prefix} Using alpha channel for PNG composite")
                        background.paste(img, mask=alpha_channel)
                    else:
                        if is_png and log_prefix:
                            app.logger.info(f"{log_prefix} No alpha channel for PNG composite")
                        background.paste(img)
                        
                    img = background
                    
                    if is_png and log_prefix:
                        app.logger.info(f"{log_prefix} PNG background compositing completed")
                elif img.mode != 'RGB':
                    if is_png and log_prefix:
                        app.logger.info(f"{log_prefix} Converting PNG from {img.mode} to RGB directly")
                    img = img.convert('RGB')
                
                # Create thumbnail with proper aspect ratio
                if is_png and log_prefix:
                    app.logger.info(f"{log_prefix} Resizing PNG to {size}")
                try:
                    img.thumbnail(size, Image.Resampling.LANCZOS)
                except Exception as resize_err:
                    if is_png and log_prefix:
                        app.logger.error(f"{log_prefix} Error during PNG resize: {str(resize_err)}")
                        app.logger.info(f"{log_prefix} Trying alternative resize method")
                    # Try alternative resize method
                    img = img.resize((min(img.width, size[0]), min(img.height, size[1])), Image.Resampling.BILINEAR)
                
                # Create a new image with the exact size (add padding if needed)
                thumb = Image.new('RGB', size, (255, 255, 255))
                
                # Calculate position to center the image
                x = (size[0] - img.size[0]) // 2
                y = (size[1] - img.size[1]) // 2
                
                thumb.paste(img, (x, y))

                # Ensure the thumbnail path ends with .jpg
                if not thumbnail_path.lower().endswith('.jpg'):
                    thumbnail_path = os.path.splitext(thumbnail_path)[0] + '.jpg'

                # Ensure target directory exists
                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

                # Save with optimization
                thumb.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                return True
        except Exception as img_err:
            # Special handling for corrupted PNGs
            if is_png and log_prefix:
                app.logger.error(f"{log_prefix} Error opening PNG with PIL: {str(img_err)}")
                app.logger.error(f"{log_prefix} Error type: {type(img_err).__name__}")
                
                # Log traceback for PNG errors
                import io
                tb_output = io.StringIO()
                traceback.print_exc(file=tb_output)
                app.logger.error(f"{log_prefix} Image open traceback:\n{tb_output.getvalue()}")
                
                # Try to fix the PNG if possible
                app.logger.info(f"{log_prefix} Attempting to fix corrupt PNG")
                try:
                    # Create a placeholder thumbnail since we can't process this PNG
                    thumb = Image.new('RGB', size, (200, 200, 200))
                    # Add text indicating error
                    from PIL import ImageDraw, ImageFont
                    draw = ImageDraw.Draw(thumb)
                    text = "PNG Error"
                    # Use default font since we can't rely on specific fonts
                    draw.text((size[0]//4, size[1]//2), text, fill=(0, 0, 0))
                    # Continue with saving this placeholder
                    app.logger.info(f"{log_prefix} Created placeholder for corrupt PNG")
                except Exception as fix_err:
                    app.logger.error(f"{log_prefix} Failed to create PNG placeholder: {str(fix_err)}")
                    raise img_err  # Re-raise the original error if we couldn't create a placeholder
            else:
                # For non-PNG files, just propagate the error
                raise
            if not thumbnail_path.lower().endswith('.jpg'):
                thumbnail_path = os.path.splitext(thumbnail_path)[0] + '.jpg'
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            # Save with optimization
            thumb.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            return True
            
    except Exception as e:
        print(f"Error creating image thumbnail for {image_path}: {str(e)}")
        return False


def create_video_thumbnail(video_path, thumbnail_path, size):
    """
    Create a thumbnail for a video file using ffmpeg.
    
    Args:
        video_path (str): Path to the original video
        thumbnail_path (str): Path where the thumbnail should be saved
        size (tuple): Thumbnail size as (width, height)
        
    Returns:
        bool: True if thumbnail was created successfully, False otherwise
    """
    try:
        # Use ffmpeg to extract a frame from the video (at 1 second)
        cmd = [
            'ffmpeg', 
            '-i', video_path,
            '-ss', '00:00:01.000',  # Extract frame at 1 second
            '-vframes', '1',
            '-y',  # Overwrite output file
            thumbnail_path + '.temp.jpg'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(thumbnail_path + '.temp.jpg'):
            # Now resize the extracted frame using PIL
            success = create_image_thumbnail(thumbnail_path + '.temp.jpg', thumbnail_path, size)
            
            # Clean up temporary file
            try:
                os.remove(thumbnail_path + '.temp.jpg')
            except:
                pass
                
            return success
        else:
            print(f"ffmpeg failed for {video_path}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error creating video thumbnail for {video_path}: {str(e)}")
        return False


def generate_optimized_versions(filename, max_original_width=500, target_size_kb=80, debug_prefix=""):
    """
    Generate thumbnail and preview versions of uploaded files.
    Convert all image files to JPG format.
    Also resizes and compresses the original image to save storage space.
    
    Args:
        filename (str): Name of the uploaded file
        max_original_width (int): Maximum width for the original image (default: 500px)
        target_size_kb (int): Target file size in kilobytes (default: 80KB)
        
    Returns:
        dict: Dictionary with paths to generated files
    """
    # Create a process ID for logging
    process_id = str(uuid.uuid4())[:6]
    log_prefix = f"[Optimize-{process_id}][{filename}]"
    app.logger.info(f"{log_prefix} Starting optimization")
    
    # Make sure all required directories exist
    for directory in [app.config['UPLOAD_FOLDER'], app.config['THUMBNAIL_FOLDER'], app.config['PREVIEW_FOLDER']]:
        os.makedirs(directory, exist_ok=True)
    
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    # Fallback to production path if dev path missing
    if not os.path.exists(original_path):
        prod_upload = "/var/Inventarsystem/Web/uploads"
        alt_path = os.path.join(prod_upload, filename)
        if os.path.exists(alt_path):
            original_path = alt_path
    
    # Generate file paths
    name_part, ext = os.path.splitext(filename)
    ext = ext.lower()
    is_jpg_ext = ext in ('.jpg', '.jpeg')
    # If already a JPG, keep filename to avoid same-file writes
    converted_filename = filename if is_jpg_ext else f"{name_part}.jpg"
    converted_path = os.path.join(app.config['UPLOAD_FOLDER'], converted_filename)
    thumbnail_filename = f"{name_part}_thumb.jpg"
    preview_filename = f"{name_part}_preview.jpg"
    
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
    preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
    # Fallback to production directories if dev ones missing
    if not os.path.exists(thumbnail_path):
        prod_thumbs = "/var/Inventarsystem/Web/thumbnails"
        alt_thumb = os.path.join(prod_thumbs, thumbnail_filename)
        if os.path.exists(alt_thumb):
            thumbnail_path = alt_thumb
    if not os.path.exists(preview_path):
        prod_previews = "/var/Inventarsystem/Web/previews"
        alt_prev = os.path.join(prod_previews, preview_filename)
        if os.path.exists(alt_prev):
            preview_path = alt_prev
    # Fallbacks for production directories if needed
    if not os.path.exists(os.path.dirname(thumbnail_path)):
        prod_thumbs = "/var/Inventarsystem/Web/thumbnails"
        if os.path.exists(prod_thumbs):
            thumbnail_path = os.path.join(prod_thumbs, thumbnail_filename)
    if not os.path.exists(os.path.dirname(preview_path)):
        prod_previews = "/var/Inventarsystem/Web/previews"
        if os.path.exists(prod_previews):
            preview_path = os.path.join(prod_previews, preview_filename)
    
    result = {
        'original': converted_filename,  # Use JPG name; if already JPG, this equals input
        'thumbnail': None,
        'preview': None,
        'is_image': False,
        'is_video': False,
        'success': False
    }
    
    # Check if the file actually exists
    if not os.path.exists(original_path):
        app.logger.error(f"{log_prefix} Original file not found: {original_path}")
        
        # Check if we need to use a placeholder
        placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.svg')
        if not os.path.exists(placeholder_path):
            placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
        # Also check production static dir
        if not os.path.exists(placeholder_path):
            prod_static = "/var/Inventarsystem/Web/static/img"
            fallback_svg = os.path.join(prod_static, 'no-image.svg')
            fallback_png = os.path.join(prod_static, 'no-image.png')
            if os.path.exists(fallback_svg):
                placeholder_path = fallback_svg
            elif os.path.exists(fallback_png):
                placeholder_path = fallback_png
            
        if os.path.exists(placeholder_path):
            app.logger.info(f"{log_prefix} Using placeholder image instead")
            try:
                # Copy placeholder to uploads folder with the original filename
                shutil.copy2(placeholder_path, original_path)
                # Also create thumbnails
                shutil.copy2(placeholder_path, thumbnail_path)
                shutil.copy2(placeholder_path, preview_path)
                result['original'] = filename
                result['thumbnail'] = thumbnail_filename
                result['preview'] = preview_filename
                result['is_placeholder'] = True
                result['success'] = True
                return result
            except Exception as e:
                app.logger.error(f"{log_prefix} Failed to use placeholder: {str(e)}")
                return result
        else:
            app.logger.error(f"{log_prefix} No placeholder found, cannot continue")
            return result
    
    # Check if it's an image or video file
    is_png = filename.lower().endswith('.png')
    
    if is_image_file(filename):
        result['is_image'] = True
        app.logger.info(f"{log_prefix} Processing as image file")
        
        # Special logging for PNG files
        if is_png:
            if debug_prefix:
                app.logger.info(f"{debug_prefix} Processing PNG in optimization function")
            else:
                app.logger.info(f"PNG DEBUG: {log_prefix} Processing PNG in optimization function")
    elif is_video_file(filename):
        result['is_video'] = True
        app.logger.info(f"{log_prefix} Processing as video file")
        
        # Create video thumbnail
        try:
            if create_video_thumbnail(original_path, thumbnail_path, THUMBNAIL_SIZE):
                result['thumbnail'] = thumbnail_filename
                app.logger.info(f"{log_prefix} Created video thumbnail")
            
            # Create video preview
            if create_video_thumbnail(original_path, preview_path, PREVIEW_SIZE):
                result['preview'] = preview_filename
                app.logger.info(f"{log_prefix} Created video preview")
                
            result['success'] = True
            return result
        except Exception as e:
            app.logger.error(f"{log_prefix} Failed to create video thumbnails: {str(e)}")
            # Continue with regular processing as fallback
    else:
        app.logger.info(f"{log_prefix} Not an image or video file, skipping optimization")
        return result
    
    try:
        # Get file info before processing
        original_size = os.path.getsize(original_path)
        app.logger.info(f"{log_prefix} Original size: {original_size/1024:.1f}KB")
        
    # Try to open and process the image
        try:
            with Image.open(original_path) as img:
                # Special handling for PNG
                is_png = filename.lower().endswith('.png')
                if is_png:
                    debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                    app.logger.info(f"{debug_msg} Processing PNG image in optimization function")
                    app.logger.info(f"{debug_msg} PNG details - Format: {img.format}, Mode: {img.mode}")
                
                # Log original dimensions
                original_width, original_height = img.size
                app.logger.info(f"{log_prefix} Original dimensions: {original_width}x{original_height}")
                
                # Resize if needed
                resized = False
                if original_width > max_original_width:
                    try:
                        scaling_factor = max_original_width / original_width
                        new_width = max_original_width
                        new_height = int(original_height * scaling_factor)
                        # Resize with high quality resampling
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        app.logger.info(f"{log_prefix} Resized to {new_width}x{new_height}")
                        if is_png:
                            app.logger.info(f"{debug_msg} PNG resized to {new_width}x{new_height}")
                        resized = True
                    except Exception as e:
                        app.logger.error(f"{log_prefix} Resize failed: {str(e)}")
                        if is_png:
                            app.logger.error(f"{debug_msg} PNG resize failed: {str(e)}")
                            app.logger.error(f"{debug_msg} Error type: {type(e).__name__}")
                        # Continue without resizing
                
                # Handle color mode conversion
                try:
                    original_mode = img.mode
                    if img.mode in ('RGBA', 'LA', 'P'):
                        app.logger.info(f"{log_prefix} Converting from {img.mode} to RGB")
                        
                        if is_png:
                            debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                            app.logger.info(f"{debug_msg} PNG has transparency (mode: {img.mode})")
                            
                            # Special handling for PNG with transparency
                            if img.mode == 'RGBA' or img.mode == 'LA':
                                app.logger.info(f"{debug_msg} Preserving PNG transparency during conversion")
                                # Try to preserve alpha during conversion by using a white background
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'P':
                                    app.logger.info(f"{debug_msg} Converting PNG from P to RGBA first")
                                    img = img.convert('RGBA')
                                
                                # Get alpha channel if available
                                alpha = None
                                if img.mode == 'RGBA':
                                    alpha = img.split()[3]
                                elif img.mode == 'LA':
                                    alpha = img.split()[1]
                                
                                # Paste with alpha mask
                                if alpha:
                                    app.logger.info(f"{debug_msg} PNG using alpha channel for paste")
                                    background.paste(img, mask=alpha)
                                else:
                                    app.logger.info(f"{debug_msg} PNG no alpha channel found, using regular paste")
                                    background.paste(img)
                                
                                img = background
                            else:
                                # For other modes like P
                                app.logger.info(f"{debug_msg} Standard conversion for PNG mode {img.mode}")
                                img = img.convert('RGB')
                        else:
                            # Standard conversion for non-PNG files
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                            img = background
                    elif img.mode != 'RGB':
                        app.logger.info(f"{log_prefix} Converting from {img.mode} to RGB")
                        if is_png:
                            debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                            app.logger.info(f"{debug_msg} Converting PNG from {img.mode} to RGB")
                        img = img.convert('RGB')
                except Exception as e:
                    app.logger.error(f"{log_prefix} Mode conversion failed: {str(e)}")
                    if is_png:
                        debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                        app.logger.error(f"{debug_msg} PNG mode conversion failed: {str(e)}")
                        app.logger.error(f"{debug_msg} Error type: {type(e).__name__}")
                        traceback.print_exc()
                    
                    # Try a simpler conversion method as fallback
                    try:
                        app.logger.info(f"{log_prefix} Attempting simple RGB conversion as fallback")
                        img = img.convert('RGB')
                        if is_png:
                            debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                            app.logger.info(f"{debug_msg} Simple PNG RGB conversion fallback")
                    except Exception as conv_err:
                        if is_png:
                            debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                            app.logger.error(f"{debug_msg} All PNG conversion methods failed: {str(conv_err)}")
                        # If conversion fails entirely, we'll save without conversion
                        pass
                
                # Save as JPG with compression to target file size
                try:
                    # Get optimal quality setting to reach target size
                    quality = get_optimal_image_quality(img, target_size_kb=target_size_kb)
                    app.logger.info(f"{log_prefix} Using quality setting: {quality}")
                    
                    if is_png:
                        debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                        app.logger.info(f"{debug_msg} Converting PNG to JPG with quality: {quality}")
                        app.logger.info(f"{debug_msg} PNG details before conversion - Mode: {img.mode}, Size: {img.size}, Bands: {img.getbands()}")
                        
                        # Special handling for PNG conversion
                        try:
                            # For PNGs, we might want to try a special save method first
                            temp_converted_path = f"{converted_path}.temp"
                            
                            # Additional debugging for problem PNGs
                            try:
                                # Check for transparency issues
                                has_transparency = False
                                if img.mode == 'RGBA':
                                    alpha = img.split()[3]
                                    has_transparency = alpha.getextrema()[0] < 255
                                    app.logger.info(f"{debug_msg} PNG has alpha transparency: {has_transparency}")
                                elif img.mode == 'P' and 'transparency' in img.info:
                                    has_transparency = True
                                    app.logger.info(f"{debug_msg} PNG has palette transparency")
                                    
                                if has_transparency:
                                    app.logger.info(f"{debug_msg} Handling PNG transparency for conversion")
                                    # Create a white background layer first
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    if img.mode == 'P':
                                        img = img.convert('RGBA')
                                    
                                    # Composite with alpha mask if available
                                    alpha_mask = None
                                    if img.mode == 'RGBA':
                                        alpha_mask = img.split()[3]
                                    
                                    background.paste(img, mask=alpha_mask)
                                    img = background
                                    app.logger.info(f"{debug_msg} PNG transparency handled, now in mode: {img.mode}")
                            except Exception as trans_err:
                                app.logger.error(f"{debug_msg} Error handling PNG transparency: {str(trans_err)}")
                                # Continue with conversion anyway
                            
                            # Try to ensure we have RGB mode
                            if img.mode != 'RGB':
                                app.logger.info(f"{debug_msg} Converting PNG from {img.mode} to RGB before save")
                                img = img.convert('RGB')
                            
                            # Save with high quality first to preserve details
                            img.save(temp_converted_path, 'JPEG', quality=95, optimize=True)
                            app.logger.info(f"{debug_msg} Initial PNG to JPG conversion successful")
                            
                            # Verify the temporary file
                            if os.path.exists(temp_converted_path) and os.path.getsize(temp_converted_path) > 0:
                                app.logger.info(f"{debug_msg} Temp JPG file size: {os.path.getsize(temp_converted_path)/1024:.1f}KB")
                                
                                # Now optimize the saved JPG to target size
                                with Image.open(temp_converted_path) as temp_img:
                                    temp_img.save(converted_path, 'JPEG', quality=quality, optimize=True)
                                    
                                # Remove temp file
                                if os.path.exists(temp_converted_path):
                                    os.remove(temp_converted_path)
                                    
                                app.logger.info(f"{debug_msg} PNG converted to JPG and optimized successfully: {os.path.getsize(converted_path)/1024:.1f}KB")
                            else:
                                app.logger.error(f"{debug_msg} Temp JPG file missing or zero size")
                                raise Exception("Temporary conversion file missing or empty")
                        except Exception as png_save_err:
                            app.logger.error(f"{debug_msg} PNG special conversion failed: {str(png_save_err)}")
                            app.logger.error(f"{debug_msg} Error type: {type(png_save_err).__name__}")
                            
                            # Log traceback for PNG errors
                            import io
                            tb_output = io.StringIO()
                            traceback.print_exc(file=tb_output)
                            app.logger.error(f"{debug_msg} PNG conversion traceback:\n{tb_output.getvalue()}")
                            
                            # Fall back to standard method
                            app.logger.info(f"{debug_msg} Trying direct PNG to JPG conversion...")
                            
                            # Try to ensure we have RGB mode
                            if img.mode != 'RGB':
                                app.logger.info(f"{debug_msg} Converting PNG from {img.mode} to RGB for fallback")
                                img = img.convert('RGB')
                                
                            img.save(converted_path, 'JPEG', quality=quality, optimize=True)
                            app.logger.info(f"{debug_msg} Direct PNG to JPG conversion successful")
                    else:
                        # Standard save for non-PNG images
                        if not is_jpg_ext:
                            # Only create a new JPG if source wasn't already JPG
                            img.save(converted_path, 'JPEG', quality=quality, optimize=True)
                            app.logger.info(f"{log_prefix} Saved optimized JPG: {converted_path}")
                        else:
                            # Already a JPG: don't overwrite original; we'll use it for thumbs
                            app.logger.info(f"{log_prefix} Original is already JPG; skip in-place re-save")
                        
                except Exception as save_err:
                    app.logger.error(f"{log_prefix} Failed to save optimized JPG: {str(save_err)}")
                    if is_png:
                        debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                        app.logger.error(f"{debug_msg} Failed to save PNG as JPG: {str(save_err)}")
                        app.logger.error(f"{debug_msg} Error type: {type(save_err).__name__}")
                        
                        # Log traceback for PNG errors
                        import io
                        tb_output = io.StringIO()
                        traceback.print_exc(file=tb_output)
                        app.logger.error(f"{debug_msg} PNG save traceback:\n{tb_output.getvalue()}")
                        
                        # Try a more direct approach for problematic PNGs
                        try:
                            app.logger.info(f"{debug_msg} Attempting last resort PNG conversion method...")
                            # Try to ensure we have RGB mode
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            # Use lowest-level save method
                            img.save(converted_path, 'JPEG', quality=85)
                            app.logger.info(f"{debug_msg} Last resort PNG conversion successful")
                        except Exception as final_err:
                            app.logger.error(f"{debug_msg} All PNG conversion methods failed: {str(final_err)}")
                            # Give up and let the code continue to next error handling step
                    
                    # Try with default quality as fallback (only when not already JPG)
                    try:
                        if not is_jpg_ext:
                            app.logger.info(f"{log_prefix} Attempting save with default quality")
                            img.save(converted_path, 'JPEG', quality=85)
                            app.logger.info(f"{log_prefix} Saved JPG with default quality")
                        else:
                            app.logger.info(f"{log_prefix} Skipping fallback save; original is JPG and won't be overwritten")
                    except Exception as default_save_err:
                        if is_png:
                            debug_msg = debug_prefix if debug_prefix else f"PNG DEBUG: {log_prefix}"
                            app.logger.error(f"{debug_msg} PNG fallback save also failed: {str(default_save_err)}")
                        
                        # If JPG conversion fails entirely and different path, copy original
                        if not is_jpg_ext and os.path.abspath(original_path) != os.path.abspath(converted_path):
                            shutil.copy2(original_path, converted_path)
                            app.logger.warning(f"{log_prefix} Used original file without optimization")
                    
                    # Compare file sizes
                    if not is_jpg_ext and os.path.exists(converted_path):
                        new_size = os.path.getsize(converted_path)
                        reduction = (1 - (new_size / original_size)) * 100 if original_size > 0 else 0
                        app.logger.info(f"{log_prefix} Size reduction: {original_size/1024:.1f}KB -> {new_size/1024:.1f}KB ({reduction:.1f}%)")
                    
                    # Remove the original non-JPG file if it was converted or resized
                    if not is_jpg_ext and os.path.exists(converted_path) and (not filename.lower().endswith('.jpg') or resized):
                        try:
                            os.remove(original_path)
                            app.logger.info(f"{log_prefix} Removed original file after conversion")
                        except Exception as e:
                            app.logger.warning(f"{log_prefix} Error removing original file: {str(e)}")
                    
                except Exception as e:
                    app.logger.error(f"{log_prefix} Compression error: {str(e)}")
                    # Use original file if optimization fails
                    if not os.path.exists(converted_path):
                        shutil.copy2(original_path, converted_path)
                        app.logger.warning(f"{log_prefix} Used original file as fallback")
                
                # Use the converted file for thumbnails if it exists
                # If we produced a converted JPG (non-JPG source), use it as the basis for thumbs
                if not is_jpg_ext and os.path.exists(converted_path):
                    original_path = converted_path
        
        except Exception as e:
            app.logger.error(f"{log_prefix} Failed to process image: {str(e)}")
            traceback.print_exc()
            # Just copy the original file as is
            if not is_jpg_ext and os.path.exists(original_path) and not os.path.exists(converted_path):
                try:
                    shutil.copy2(original_path, converted_path)
                    app.logger.warning(f"{log_prefix} Used original file after processing error")
                except Exception as copy_err:
                    app.logger.error(f"{log_prefix} Failed to copy original file: {str(copy_err)}")
        
        # Create thumbnail - with multiple fallbacks
        thumbnail_created = False
        try:
            if create_image_thumbnail(original_path, thumbnail_path, THUMBNAIL_SIZE):
                result['thumbnail'] = thumbnail_filename
                thumbnail_created = True
                app.logger.info(f"{log_prefix} Created thumbnail successfully")
        except Exception as thumb_err:
            app.logger.error(f"{log_prefix} Thumbnail creation failed: {str(thumb_err)}")
            
            # Try direct copy if thumbnail creation fails
            if not thumbnail_created:
                try:
                    # Just copy the original (or converted) file
                    shutil.copy2(original_path, thumbnail_path)
                    result['thumbnail'] = thumbnail_filename
                    thumbnail_created = True
                    app.logger.warning(f"{log_prefix} Used original as thumbnail after error")
                except Exception as copy_err:
                    app.logger.error(f"{log_prefix} Failed to copy original as thumbnail: {str(copy_err)}")
            
            # If all else fails, try a very simple PIL thumbnail as last resort
            if not thumbnail_created:
                try:
                    with Image.open(original_path) as img:
                        img.thumbnail(THUMBNAIL_SIZE)
                        img.save(thumbnail_path, 'JPEG')
                        result['thumbnail'] = thumbnail_filename
                        thumbnail_created = True
                        app.logger.warning(f"{log_prefix} Created thumbnail with fallback method")
                except Exception as last_err:
                    app.logger.error(f"{log_prefix} All thumbnail creation methods failed: {str(last_err)}")
        
        # Create preview - with multiple fallbacks
        preview_created = False
        try:
            if create_image_thumbnail(original_path, preview_path, PREVIEW_SIZE):
                result['preview'] = preview_filename
                preview_created = True
                app.logger.info(f"{log_prefix} Created preview successfully")
        except Exception as prev_err:
            app.logger.error(f"{log_prefix} Preview creation failed: {str(prev_err)}")
            
            # Try direct copy if preview creation fails
            if not preview_created:
                try:
                    # Just copy the original (or converted) file
                    shutil.copy2(original_path, preview_path)
                    result['preview'] = preview_filename
                    preview_created = True
                    app.logger.warning(f"{log_prefix} Used original as preview after error")
                except Exception as copy_err:
                    app.logger.error(f"{log_prefix} Failed to copy original as preview: {str(copy_err)}")
            
            # If all else fails, try a very simple PIL thumbnail as last resort
            if not preview_created:
                try:
                    with Image.open(original_path) as img:
                        img.thumbnail(PREVIEW_SIZE)
                        img.save(preview_path, 'JPEG')
                        result['preview'] = preview_filename
                        preview_created = True
                        app.logger.warning(f"{log_prefix} Created preview with fallback method")
                except Exception as last_err:
                    app.logger.error(f"{log_prefix} All preview creation methods failed: {str(last_err)}")
        
        # Mark success if we have at least the original or converted file
        if os.path.exists(original_path) or os.path.exists(converted_path):
            result['success'] = True
            app.logger.info(f"{log_prefix} Optimization completed successfully")
            
            # Log verification of all created files
            for file_type, file_path in [
                ('Original', original_path),
                ('Converted', converted_path),
                ('Thumbnail', thumbnail_path),
                ('Preview', preview_path)
            ]:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path) / 1024.0  # KB
                    app.logger.info(f"{log_prefix} {file_type}: {os.path.basename(file_path)} ({file_size:.1f}KB)")
                else:
                    app.logger.warning(f"{log_prefix} {file_type} file missing: {os.path.basename(file_path)}")
            
        return result
        
    except Exception as e:
        app.logger.error(f"{log_prefix} Unhandled exception in optimization: {str(e)}")
        traceback.print_exc()
        
        # If anything went wrong but the original file exists, just use it
        if os.path.exists(original_path):
            try:
                # Copy original to all required outputs as last resort
                for target_path in [converted_path, thumbnail_path, preview_path]:
                    if not os.path.exists(os.path.dirname(target_path)):
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(original_path, target_path)
                
                result['original'] = filename
                result['thumbnail'] = thumbnail_filename
                result['preview'] = preview_filename
                result['success'] = True
                result['recovery'] = True
                app.logger.warning(f"{log_prefix} Recovery completed: using original file for all outputs")
                return result
            except Exception as recovery_err:
                app.logger.error(f"{log_prefix} Recovery failed: {str(recovery_err)}")
        
        return result

def get_thumbnail_info(filename):
    """
    Get thumbnail and preview information for a file.
    Creates thumbnails if they don't exist.
    
    Args:
        filename (str): Original filename
        
    Returns:
        dict: Dictionary with thumbnail and preview information
    """
    if not filename:
        return {'has_thumbnail': False, 'has_preview': False}
    
    name_part, ext_part = os.path.splitext(filename)
    thumbnail_filename = f"{name_part}_thumb.jpg"
    preview_filename = f"{name_part}_preview.jpg"
    
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
    preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
    
    # Check if thumbnails exist, create if needed
    has_thumbnail = os.path.exists(thumbnail_path)
    has_preview = os.path.exists(preview_path)
    
    if not has_thumbnail or not has_preview:
        try:
            result = generate_optimized_versions(filename, max_original_width=500, target_size_kb=80)
            has_thumbnail = result['thumbnail'] is not None
            has_preview = result['preview'] is not None
        except Exception as e:
            print(f"Error generating thumbnails for {filename}: {str(e)}")
    
    # Make sure we're using the actual filename as it exists on disk
    # Build URLs based on the filename; routes handle prod/dev paths
    actual_thumbnail_url = f"/thumbnails/{thumbnail_filename}" if has_thumbnail else None
    actual_preview_url = f"/previews/{preview_filename}" if has_preview else None
    
    return {
        'has_thumbnail': has_thumbnail,
        'has_preview': has_preview,
        'thumbnail_url': actual_thumbnail_url,
        'preview_url': actual_preview_url,
        'original_ext': ext_part.lower(),
        'is_image': is_image_file(filename),
        'is_video': is_video_file(filename)
    }

# Mobile device detection utilities
def is_mobile_device(request):
    """Determine if the request is coming from a mobile device"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_identifiers = ['iphone', 'ipad', 'android', 'mobile', 'tablet']
    return any(identifier in user_agent for identifier in mobile_identifiers)

def is_ios_device(request):
    """Determine if the request is coming from an iOS device"""
    user_agent = request.headers.get('User-Agent', '').lower()
    return 'iphone' in user_agent or 'ipad' in user_agent or 'ipod' in user_agent

def log_mobile_action(action, request, success=True, details=None):
    """Log mobile-specific actions for debugging"""
    device_info = request.headers.get('User-Agent', 'Unknown device')
    status = "SUCCESS" if success else "FAILED"
    message = f"MOBILE {action} {status} - Device: {device_info}"
    if details:
        message += f" - Details: {details}"
    
    if success:
        app.logger.info(message)
    else:
        app.logger.error(message)
        
# Add explicit static file routes to handle CSS serving issues
@app.route('/static/<path:filename>')
def serve_static(filename):
    """
    Explicitly serve static files to resolve 403 Forbidden errors.
    This ensures CSS and JS files are properly accessible.
    
    Args:
        filename (str): The static file path
        
    Returns:
        flask.Response: The requested static file
    """
    return send_from_directory(app.static_folder, filename)

@app.route('/static/css/<filename>')
def serve_css(filename):
    """
    Explicitly serve CSS files from the static/css directory.
    
    Args:
        filename (str): Name of the CSS file to serve
        
    Returns:
        flask.Response: The requested CSS file
    """
    css_folder = os.path.join(app.static_folder, 'css')
    return send_from_directory(css_folder, filename)

@app.route('/static/js/<filename>')
def serve_js(filename):
    """
    Explicitly serve JavaScript files from the static/js directory.
    
    Args:
        filename (str): Name of the JS file to serve
        
    Returns:
        flask.Response: The requested JS file
    """
    js_folder = os.path.join(app.static_folder, 'js')
    return send_from_directory(js_folder, filename)

@app.route('/log_mobile_issue', methods=['POST'])
def log_mobile_issue():
    """
    Route for logging mobile-specific issues.
    Used for tracking and debugging mobile browser problems.
    
    Returns:
        flask.Response: JSON response with success status
    """
    try:
        # Get issue data from request
        issue_data = request.json
        
        # Add timestamp if not present
        if 'timestamp' not in issue_data:
            issue_data['timestamp'] = datetime.now().isoformat()
            
        # Format the log message
        log_message = f"MOBILE ISSUE: {issue_data.get('action', 'unknown')} - "
        log_message += f"Error: {issue_data.get('error', 'none')} - "
        log_message += f"Browser: {issue_data.get('browser', 'unknown')}"
        
        # Create a structured log entry
        log_entry = {
            'type': 'mobile_issue',
            'timestamp': issue_data.get('timestamp'),
            'data': issue_data
        }
        
        # Log to application log file
        app.logger.warning(log_message)
        
        # Store in database for analytics
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        logs_collection = db['system_logs']
        logs_collection.insert_one(log_entry)
        client.close()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error logging mobile issue: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def delete_item_images(filenames):
    """
    Delete all images associated with an item (original, thumbnail, preview).
    
    Args:
        filenames (list): List of image filenames to delete
        
    Returns:
        dict: Statistics of deleted files (counts of originals, thumbnails, previews, errors)
    """
    stats = {
        'originals': 0,
        'thumbnails': 0,
        'previews': 0,
        'errors': 0
    }
    
    if not filenames:
        return stats
        
    for filename in filenames:
        if not filename:
            continue
            
        try:
            # Generate paths based on filename pattern
            name_part = os.path.splitext(filename)[0]
            
            # Original file (may be JPG converted)
            original_jpg = f"{name_part}.jpg"
            original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_jpg)
            
            # Also try with original extension in case conversion didn't happen
            original_orig_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Thumbnail and preview
            thumbnail_filename = f"{name_part}_thumb.jpg"
            preview_filename = f"{name_part}_preview.jpg"
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
            preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
            
            # Delete original file(s)
            if os.path.exists(original_path):
                os.remove(original_path)
                stats['originals'] += 1
            elif os.path.exists(original_orig_path):
                os.remove(original_orig_path)
                stats['originals'] += 1
                
            # Delete thumbnail
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                stats['thumbnails'] += 1
                
            # Delete preview
            if os.path.exists(preview_path):
                os.remove(preview_path)
                stats['previews'] += 1
                
        except Exception as e:
            app.logger.error(f"Error deleting image files for {filename}: {str(e)}")
            stats['errors'] += 1
    
    return stats

def get_optimal_image_quality(img, target_size_kb=80):
    """
    Find the optimal JPEG quality setting to achieve a target file size.
    Uses a binary search approach to efficiently find the best quality.
    
    Args:
        img (PIL.Image): The PIL Image object
        target_size_kb (int): Target file size in kilobytes
        
    Returns:
        int: Quality setting (1-95)
    """
    import io
    
    # Initialize search range
    min_quality = 30  # We don't want to go lower than this
    max_quality = 95  # No need to go higher than this
    best_quality = 80  # Default quality
    best_diff = float('inf')
    target_size_bytes = target_size_kb * 1024
    
    # Binary search for optimal quality
    for _ in range(5):  # 5 iterations is usually enough
        quality = (min_quality + max_quality) // 2
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        size = buffer.tell()
        
        # Check how close we are to target size
        diff = abs(size - target_size_bytes)
        if diff < best_diff:
            best_diff = diff
            best_quality = quality
        
        # Adjust search range
        if size > target_size_bytes:
            max_quality = quality - 1
        else:
            min_quality = quality + 1
            
        # If we’re within 10% of target, that’s good enough
        if abs(size - target_size_bytes) < (target_size_bytes * 0.1):
            return quality
    
    return best_quality

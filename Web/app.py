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
import io
import qrcode
from qrcode.constants import ERROR_CORRECT_L
import threading
import sys
import shutil
import uuid
from PIL import Image, ImageOps
import mimetypes
import subprocess

# Set base directory for absolute path references
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Initialize Flask application
app = Flask(__name__, static_folder='static')  # Correctly set static folder
app.secret_key = 'Hsse783942h2342f342342i34hwebf8'  # For production, use a secure key!
app.debug = False  # Debug disabled in production
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['THUMBNAIL_FOLDER'] = os.path.join(BASE_DIR, 'thumbnails')
app.config['PREVIEW_FOLDER'] = os.path.join(BASE_DIR, 'previews')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v', '3gp'}
QR_CODE_FOLDER = os.path.join(BASE_DIR, 'QRCodes')
app.config['QR_CODE_FOLDER'] = QR_CODE_FOLDER

# Thumbnail sizes
THUMBNAIL_SIZE = (150, 150)  # Small thumbnails for card view
PREVIEW_SIZE = (400, 400)    # Medium previews for modal/detail view

__version__ = '1.2.4'  # Version of the application
Host = '0.0.0.0'
Port = 8080

# Default MongoDB settings
MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
MONGODB_DB = 'Inventarsystem'
SCHEDULER_INTERVAL = 1  # minutes
SSL_CERT = 'ssl_certs/inventarsystem.crt'
SSL_KEY = 'ssl_certs/inventarsystem.key'


# Import config
try:
    with open(os.path.join(BASE_DIR, '..', 'config.json'), 'r') as f:
        conf = json.load(f)
    
    # Check if config file has the required keys
    required_keys = ['dbg', 'key', 'ver', 'host', 'port']
    for key in required_keys:
        if key not in conf:
            print(f"Warning: Missing required key in config: {key}. Using default value.")
    
    # Set application variables from config or use defaults
    __version__ = conf.get('ver', '1.2.4')
    app.debug = conf.get('dbg', False)
    app.secret_key = str(conf.get('key', 'Hsse783942h2342f342342i34hwebf8'))  # Convert to string
    Host = conf.get('host', '0.0.0.0')
    Port = conf.get('port', 443)
    
    # Get school periods from config or use defaults
    SCHOOL_PERIODS = conf.get('schoolPeriods', {
        "1": { "start": "08:00", "end": "08:45", "label": "1. Stunde (08:00 - 08:45)" },
        "2": { "start": "08:45", "end": "09:30", "label": "2. Stunde (08:45 - 09:30)" },
        "3": { "start": "09:45", "end": "10:30", "label": "3. Stunde (09:45 - 10:30)" },
        "4": { "start": "10:30", "end": "11:15", "label": "4. Stunde (10:30 - 11:15)" },
        "5": { "start": "11:30", "end": "12:15", "label": "5. Stunde (11:30 - 12:15)" },
        "6": { "start": "12:15", "end": "13:00", "label": "6. Stunde (12:15 - 13:00)" },
        "7": { "start": "13:30", "end": "14:15", "label": "7. Stunde (13:30 - 14:15)" },
        "8": { "start": "14:15", "end": "15:00", "label": "8. Stunde (14:15 - 15:00)" },
        "9": { "start": "15:15", "end": "16:00", "label": "9. Stunde (15:15 - 16:00)" },
        "10": { "start": "16:00", "end": "16:45", "label": "10. Stunde (16:00 - 16:45)" }
    })
    
    # Get additional configurable settings
    # MongoDB settings
    mongodb_settings = conf.get('mongodb', {})
    MONGODB_HOST = mongodb_settings.get('host', 'localhost')
    MONGODB_PORT = mongodb_settings.get('port', 27017)
    MONGODB_DB = mongodb_settings.get('db', 'Inventarsystem')
    
    # File extensions
    extensions = conf.get('allowed_extensions', ['png', 'jpg', 'jpeg', 'gif'])
    app.config['ALLOWED_EXTENSIONS'] = set(extensions)
    
    # Scheduler settings
    scheduler_settings = conf.get('scheduler', {})
    SCHEDULER_INTERVAL = scheduler_settings.get('interval_minutes', 1)
    
    # SSL settings
    ssl_settings = conf.get('ssl', {})
    SSL_CERT = ssl_settings.get('cert', 'ssl_certs/cert.pem')
    SSL_KEY = ssl_settings.get('key', 'ssl_certs/key.pem')
    
except FileNotFoundError:
    print("Config file not found. Using default values.")
    # Default configuration
    __version__ = '1.2.4'
    app.debug = False
    app.secret_key = 'Hsse783942h2342f342342i34hwebf8'
    Host = '0.0.0.0'
    Port = 443
    # Default school periods
    SCHOOL_PERIODS = {
        "1": { "start": "08:00", "end": "08:45", "label": "1. Stunde (08:00 - 08:45)" },
        "2": { "start": "08:45", "end": "09:30", "label": "2. Stunde (08:45 - 09:30)" },
        "3": { "start": "09:45", "end": "10:30", "label": "3. Stunde (09:45 - 10:30)" },
        "4": { "start": "10:30", "end": "11:15", "label": "4. Stunde (10:30 - 11:15)" },
        "5": { "start": "11:30", "end": "12:15", "label": "5. Stunde (11:30 - 12:15)" },
        "6": { "start": "12:15", "end": "13:00", "label": "6. Stunde (12:15 - 13:00)" },
        "7": { "start": "13:30", "end": "14:15", "label": "7. Stunde (13:30 - 14:15)" },
        "8": { "start": "14:15", "end": "15:00", "label": "8. Stunde (14:15 - 15:00)" },
        "9": { "start": "15:15", "end": "16:00", "label": "9. Stunde (15:15 - 16:00)" },
        "10": { "start": "16:00", "end": "16:45", "label": "10. Stunde (16:00 - 16:45)" }
    }
    
except json.JSONDecodeError:
    print("Error: Config file contains invalid JSON. Using default values.")
    # Default configuration
    __version__ = '1.2.4'
    app.debug = False
    app.secret_key = 'Hsse783942h2342f342342i34hwebf8'
    Host = '0.0.0.0'
    Port = 443
    # Default school periods
    SCHOOL_PERIODS = {
        "1": { "start": "08:00", "end": "08:45", "label": "1. Stunde (08:00 - 08:45)" },
        "2": { "start": "08:45", "end": "09:30", "label": "2. Stunde (08:45 - 09:30)" },
        "3": { "start": "09:45", "end": "10:30", "label": "3. Stunde (09:45 - 10:30)" },
        "4": { "start": "10:30", "end": "11:15", "label": "4. Stunde (10:30 - 11:15)" },
        "5": { "start": "11:30", "end": "12:15", "label": "5. Stunde (11:30 - 12:15)" },
        "6": { "start": "12:15", "end": "13:00", "label": "6. Stunde (12:15 - 13:00)" },
        "7": { "start": "13:30", "end": "14:15", "label": "7. Stunde (13:30 - 14:15)" },
        "8": { "start": "14:15", "end": "15:00", "label": "8. Stunde (14:15 - 15:00)" },
        "9": { "start": "15:15", "end": "16:00", "label": "9. Stunde (15:15 - 16:00)" },
        "10": { "start": "16:00", "end": "16:45", "label": "10. Stunde (16:00 - 16:45)" }
    }

# Apply the configuration for general use throughout the app
APP_VERSION = __version__

@app.context_processor
def inject_version():
    """
    Makes the application version available to all templates
    """
    return {'version': APP_VERSION, 'school_periods': SCHOOL_PERIODS}

# Create necessary directories at startup
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['THUMBNAIL_FOLDER']):
    os.makedirs(app.config['THUMBNAIL_FOLDER'])
if not os.path.exists(app.config['PREVIEW_FOLDER']):
    os.makedirs(app.config['PREVIEW_FOLDER'])
if not os.path.exists(app.config['QR_CODE_FOLDER']):
    os.makedirs(app.config['QR_CODE_FOLDER'])

# Create backup directories
BACKUP_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
if not os.path.exists(BACKUP_FOLDER):
    os.makedirs(BACKUP_FOLDER)

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
    try:
        current_time = datetime.datetime.now()
        
        # Log to file for debugging
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, 'scheduler.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{current_time}] Starte automatische Statusaktualisierung...\n")
        
        print(f"[{current_time}] Starte automatische Statusaktualisierung...")
        
        # Hole alle Termine mit Status 'planned' oder 'active'
        from pymongo import MongoClient
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
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
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.datetime.now()}] {error_msg}\n")
        import traceback
        traceback.print_exc()

# Schedule jobs
scheduler = BackgroundScheduler()
scheduler.add_job(func=create_daily_backup, trigger="interval", hours=24)
# Add minute-based status updates for the Terminplaner
scheduler.add_job(func=update_appointment_statuses, trigger="interval", minutes=1)
scheduler.start()

# Register shutdown handler to stop scheduler when app is terminated
import atexit
atexit.register(lambda: scheduler.shutdown())

def allowed_file(filename):
    """
    Check if a file has an allowed extension.
    
    Args:
        filename (str): Name of the file to check
        
    Returns:
        tuple: (bool, str) - True if the file extension is allowed, False otherwise
               along with an error message if not allowed
    """
    if '.' not in filename:
        return False, f"Datei '{filename}' hat keine Dateiendung. Erlaubte Formate: {', '.join(app.config['ALLOWED_EXTENSIONS'])}"
    
    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in app.config['ALLOWED_EXTENSIONS']:
        return False, f"Datei '{filename}' hat ein nicht unterstütztes Format ({extension}). Erlaubte Formate: {', '.join(app.config['ALLOWED_EXTENSIONS'])}"
    
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
        # Check if file exists
        if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        else:
            # Check production path if development path doesn't exist
            prod_path = "/var/Inventarsystem/Web/uploads"
            if os.path.exists(os.path.join(prod_path, filename)):
                return send_from_directory(prod_path, filename)
            
            # Use a placeholder image if file not found
            placeholder_path = os.path.join(app.static_folder, 'img', 'no-image.png')
            if os.path.exists(placeholder_path):
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
        # Check if file exists
        if os.path.exists(os.path.join(app.config['THUMBNAIL_FOLDER'], filename)):
            return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename)
        else:
            # Check production path if development path doesn't exist
            prod_path = "/var/Inventarsystem/Web/thumbnails"
            if os.path.exists(os.path.join(prod_path, filename)):
                return send_from_directory(prod_path, filename)
            
            # Use a placeholder image if file not found
            return send_from_directory(app.static_folder, 'img/no-image.svg')
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
        # Check if file exists
        if os.path.exists(os.path.join(app.config['PREVIEW_FOLDER'], filename)):
            return send_from_directory(app.config['PREVIEW_FOLDER'], filename)
        else:
            # Check production path if development path doesn't exist
            prod_path = "/var/Inventarsystem/Web/previews"
            if os.path.exists(os.path.join(prod_path, filename)):
                return send_from_directory(prod_path, filename)
            
            # Use a placeholder image if file not found
            return send_from_directory(app.static_folder, 'img/no-image.svg')
    except Exception as e:
        print(f"Error serving preview {filename}: {str(e)}")
        return Response("Preview not found", status=404)


@app.route('/QRCodes/<filename>')
def qrcode_file(filename):
    """
    Serve QR code files from the QRCodes directory.
    
    Args:
        filename (str): Name of the QR code file to serve
        
    Returns:
        flask.Response: The requested QR code file or placeholder image if not found
    """
    try:
        # Check if file exists
        if os.path.exists(os.path.join(app.config['QR_CODE_FOLDER'], filename)):
            return send_from_directory(app.config['QR_CODE_FOLDER'], filename)
        else:
            # Check production path if development path doesn't exist
            prod_path = "/var/Inventarsystem/Web/QRCodes"
            if os.path.exists(os.path.join(prod_path, filename)):
                return send_from_directory(prod_path, filename)
            
            # Use a placeholder image if file not found
            return send_from_directory(app.static_folder, 'img/no-image.svg')
    except Exception as e:
        print(f"Error serving QR code {filename}: {str(e)}")
        return Response("QR code not found", status=404)


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
            app.config['QR_CODE_FOLDER'],
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
                "/var/Inventarsystem/Web/QRCodes",
                "/var/Inventarsystem/Web/static"
            ]
            
            for directory in prod_dirs:
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    return send_from_directory(directory, os.path.basename(filename))
        
        # Check if this looks like an image request
        if any(filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'gif', 'svg']):
            # Use a placeholder image if file not found
            return send_from_directory(app.static_folder, 'img/no-image.svg')
        
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
    """
    API endpoint to retrieve all inventory items.
    
    Returns:
        dict: Dictionary containing all inventory items
    """
    # Check if we should filter for available items only
    available_only = request.args.get('available_only', 'false').lower() == 'true'
    
    # Get all items
    items = it.get_items()
    
    # Get all active borrowings for lookup
    active_borrowings = {}
    try:
        all_borrowings = au.get_active_ausleihungen()
        for borrowing in all_borrowings:
            item_id = str(borrowing.get('Item'))
            if item_id:
                # Handle both regular items and exemplar items
                if '_' in item_id:  # Format is parent_id_exemplar_number
                    parent_id = item_id.split('_')[0]
                    if parent_id not in active_borrowings:
                        active_borrowings[parent_id] = []
                    active_borrowings[parent_id].append({
                        'user': borrowing.get('User'),
                        'start_date': borrowing.get('Start', '').strftime('%d.%m.%Y %H:%M') if borrowing.get('Start') else '',
                        'exemplar': borrowing.get('ExemplarData', {}).get('exemplar_number', '')
                    })
                else:
                    active_borrowings[item_id] = [{
                        'user': borrowing.get('User'),
                        'start_date': borrowing.get('Start', '').strftime('%d.%m.%Y %H:%M') if borrowing.get('Start') else ''
                    }]
    except Exception as e:
        print(f"Error fetching active borrowings: {e}")
    
    # Process items
    for item in items:
        item_id = str(item['_id'])
        
        # Add thumbnail information for images
        if 'Images' in item and item['Images']:
            item['ThumbnailInfo'] = []
            for image_filename in item['Images']:
                thumbnail_info = get_thumbnail_info(image_filename)
                item['ThumbnailInfo'].append(thumbnail_info)
        
        # Add exemplar availability info
        if 'Exemplare' in item and item['Exemplare'] > 1:
            # Get exemplar status if available
            exemplare_status = item.get('ExemplareStatus', [])
            borrowed_count = len(exemplare_status)
            available_count = item['Exemplare'] - borrowed_count
            
            item['AvailableExemplare'] = available_count
            item['BorrowedExemplare'] = borrowed_count
            
            # Count exemplars borrowed by current user
            current_user = session.get('username')
            if current_user:
                borrowed_by_me = [ex for ex in exemplare_status if ex.get('user') == current_user]
                item['BorrowedByMeCount'] = len(borrowed_by_me)
            
            # If some exemplars are available, mark the item as available
            if available_count > 0:
                item['Verfuegbar'] = True
        
        # Add borrower information if item is borrowed
        if not item.get('Verfuegbar', True):
            # Try to get detailed borrowing info
            if item_id in active_borrowings:
                borrowers = active_borrowings[item_id]
                if len(borrowers) == 1:
                    item['BorrowerInfo'] = {
                        'username': borrowers[0]['user'],
                        'borrowTime': borrowers[0]['start_date']
                    }
                else:
                    # Multiple borrowers - format differently
                    users = set(b['user'] for b in borrowers)
                    item['BorrowerInfo'] = {
                        'username': f"{len(users)} users ({', '.join(users)})",
                        'borrowTime': 'Multiple borrowing times'
                    }
            # Fallback to basic info from item record
            elif 'User' in item:
                item['BorrowerInfo'] = {
                    'username': item['User'],
                    'borrowTime': 'Unbekannt'
                }
    
    # Filter items if needed
    if available_only:
        items = [item for item in items if item.get('Verfuegbar', False) or 
                 (item.get('Exemplare', 1) > 1 and item.get('AvailableExemplare', 0) > 0)]
    
    return {'items': items}


@app.route('/get_item/<id>')
def get_item_json(id):
    """
    API endpoint to retrieve a specific item by ID.
    
    Args:
        id (str): ID of the item to retrieve
        
    Returns:
        dict: The item data or an error message
    """
    if 'username' not in session:
        return {'error': 'Not authorized', 'status': 'forbidden'}, 403
        
    item = it.get_item(id)
    if item:
        item['_id'] = str(item['_id'])  # Convert ObjectId to string
        
        # Add thumbnail information for images
        if 'Images' in item and item['Images']:
            item['ThumbnailInfo'] = []
            for image_filename in item['Images']:
                thumbnail_info = get_thumbnail_info(image_filename)
                item['ThumbnailInfo'].append(thumbnail_info)
        
        # Fetch all appointments for this item and perform client-side status verification
        try:
            # Get all appointments, not just those marked as 'planned' in the database
            all_appointments = au.get_ausleihungen()
            item_appointments = []
            
            # Filter appointments for this specific item
            for appointment in all_appointments:
                appt_item_id = appointment.get('Item')
                if appt_item_id:
                    # For exemplars, extract the parent item ID
                    parent_id = appt_item_id
                    if '_' in appt_item_id:  # Format is parent_id_exemplar_number
                        parent_id = appt_item_id.split('_')[0]
                        
                    # Check if this appointment is for the current item
                    if parent_id == id:
                        # Get verified status using client-side verification with logging
                        verified_status = au.get_current_status(
                            appointment,
                            log_changes=True,
                            user=session.get('username', None)
                        )
                        
                        # Format the appointment data
                        formatted_appointment = {
                            'id': str(appointment.get('_id')),
                            'start': appointment.get('Start'),
                            'end': appointment.get('End'),
                            'user': appointment.get('User'),
                            'notes': appointment.get('Notes', ''),
                            'period': appointment.get('Period'),
                            'status': verified_status,
                            'databaseStatus': appointment.get('Status')
                        }
                        item_appointments.append(formatted_appointment)
            
            # Sort appointments by date
            item_appointments.sort(key=lambda x: x.get('start') or datetime.datetime.now())
            
            # Add to item response
            item['PlannedAppointments'] = item_appointments
            
        except Exception as e:
            print(f"Error retrieving planned appointments: {e}")
        
        return {'item': item, 'status': 'success'}
    else:
        return {'error': 'Item not found', 'status': 'not_found'}, 404


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

    # Process any new uploaded images with better mobile handling
    image_filenames = []
    processed_count = 0
    error_count = 0
    skipped_count = 0
    
    for image in images:
        if image and image.filename:
            is_allowed, error_message = allowed_file(image.filename)
            if is_allowed:
                try:
                    # Get the file extension for content type determination
                    _, ext_part = os.path.splitext(secure_filename(image.filename))
                    
                    # Generate a completely unique filename using UUID
                    unique_id = str(uuid.uuid4())
                    timestamp = time.strftime("%Y%m%d%H%M%S")
                    
                    # New filename format with UUID to ensure uniqueness
                    saved_filename = f"{unique_id}_{timestamp}{ext_part}"
                    
                    # For iOS devices, we need special handling for the file save
                    if is_ios:
                        # Save to a temporary file first to avoid iOS stream issues
                        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{saved_filename}")
                        image.save(temp_path)
                        
                        # Validate the saved file
                        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                            # Rename to the final filename
                            final_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                            os.rename(temp_path, final_path)
                        else:
                            raise Exception("Failed to save image file (zero size or missing)")
                    else:
                        # Regular file save for non-iOS devices
                        image.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
                    
                    # Generate optimized versions (thumbnails and previews)
                    try:
                        # Log original file size before optimization
                        original_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                        original_size = os.path.getsize(original_path)
                        
                        # Get original image dimensions
                        original_dimensions = ""
                        try:
                            with Image.open(original_path) as img:
                                original_dimensions = f"{img.width}x{img.height}"
                        except:
                            pass
                        
                        # Generate optimized versions (this will also resize and compress the original)
                        # Target 80KB for a good balance between quality and size
                        generate_optimized_versions(saved_filename, max_original_width=500, target_size_kb=80)
                        
                        # Log file size after optimization
                        optimized_name = os.path.splitext(saved_filename)[0] + '.jpg'
                        optimized_path = os.path.join(app.config['UPLOAD_FOLDER'], optimized_name)
                        if os.path.exists(optimized_path):
                            optimized_size = os.path.getsize(optimized_path)
                            reduction = (1 - (optimized_size / original_size)) * 100 if original_size > 0 else 0
                            
                            # Get optimized dimensions
                            optimized_dimensions = ""
                            try:
                                with Image.open(optimized_path) as img:
                                    optimized_dimensions = f"{img.width}x{img.height}"
                            except:
                                pass
                                
                            app.logger.info(
                                f"Image optimization: {saved_filename} → {optimized_name}\n"
                                f"  Size: {original_size/1024:.1f}KB → {optimized_size/1024:.1f}KB ({reduction:.1f}% reduction)\n"
                                f"  Dimensions: {original_dimensions} → {optimized_dimensions}"
                            )
                    except Exception as e:
                        app.logger.warning(f"Warning: Could not generate optimized versions for {saved_filename}: {str(e)}")
                    
                    image_filenames.append(saved_filename)
                    processed_count += 1
                except Exception as e:
                    app.logger.error(f"Error saving image {image.filename}: {str(e)}")
                    error_count += 1
            else:
                app.logger.warning(f"Skipped file with disallowed type: {image.filename}")
                skipped_count += 1
                if not is_mobile:
                    flash(error_message, 'error')

    # Handle duplicate images if duplicating
    if duplicate_images:
        # For mobile browsers, we need to verify the duplicate images exist first
        verified_duplicates = []
        for dup_img in duplicate_images:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], dup_img)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                verified_duplicates.append(dup_img)
            else:
                app.logger.warning(f"Duplicate image not found: {dup_img}")
        
        # Create copies of verified images with new unique filenames
        duplicate_image_copies = []
        for dup_img in verified_duplicates:
            try:
                # Generate a new unique filename
                unique_id = str(uuid.uuid4())
                timestamp = time.strftime("%Y%m%d%H%M%S")
                _, ext_part = os.path.splitext(dup_img)
                new_filename = f"{unique_id}_{timestamp}{ext_part}"
                
                # Copy the image file to the new name
                src_path = os.path.join(app.config['UPLOAD_FOLDER'], dup_img)
                dst_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                shutil.copy2(src_path, dst_path)
                
                # Generate optimized versions (thumbnails and previews) for the new copy
                generate_optimized_versions(new_filename, max_original_width=500, target_size_kb=80)
                
                # Add the new filename to our list
                duplicate_image_copies.append(new_filename)
                processed_count += 1
                
                app.logger.info(f"Created copy of image {dup_img} as {new_filename}")
            except Exception as e:
                app.logger.error(f"Error creating copy of image {dup_img}: {str(e)}")
                error_count += 1
        
        # Add the new image copies to our list of filenames
        image_filenames.extend(duplicate_image_copies)

    # Handle book cover image if provided
    if book_cover_image:
        # Verify the book cover image exists
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], book_cover_image)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            image_filenames.append(book_cover_image)
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
        # Create QR code for the item
        create_qr_code(str(item_id))
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
                filename = secure_filename(image.filename)
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
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
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


def create_qr_code(id):
    """
    Generate a QR code for an item.
    The QR code contains a URL that points to the item details.
    
    Args:
        id (str): ID of the item to generate QR code for
        
    Returns:
        str: Filename of the generated QR code, or None if item not found
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_L,  # Use imported constant
        box_size=10,
        border=4,
    )
    
    # Parse and reconstruct the URL properly
    parsed_url = urlparse(request.url_root)
    
    # Force HTTPS if needed
    scheme = 'https' if parsed_url.scheme == 'http' else parsed_url.scheme
    
    # Properly reconstruct the base URL
    base_url = urlunparse((scheme, parsed_url.netloc, '', '', '', ''))
    
    # URL that will open this item directly
    item_url = f"{base_url}:{Port}/item/{id}"
    qr.add_data(item_url)
    qr.make(fit=True)

    item = it.get_item(id)
    if not item:
        return None
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Create a safe filename using a combination of item name and id
    safe_name = secure_filename(item['Name'])
    filename = f"{safe_name}_{id}.png"
    qr_path = os.path.join(app.config['QR_CODE_FOLDER'], filename)
    
    # Fix the file handling - save to file object, not string
    with open(qr_path, 'wb') as f:
        img.save(f)
    
    return filename

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
            if not username or not password:
                flash('Please fill all fields', 'error')
                return redirect(url_for('register'))
            if us.get_user(username):
                flash('User already exists', 'error')
                return redirect(url_for('register'))
            if not us.check_password_strength(password):
                flash('Password is too weak', 'error')
                return redirect(url_for('register'))
            us.add_user(username, password)







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
        for field in ['username', 'Username', 'name']:
            if field in user:
                username = user[field]
                break
                
        # Only add if not the current user and we found a username
        if username and username != session['username']:
            users_list.append({
                'username': username,
                'admin': user.get('Admin', False)
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
    
    # Delete the user
    try:
        us.delete_user(username)
        flash(f'User {username} deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('user_del'))


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
        
        # Check for conflicts
        try:
            has_conflict = au.check_booking_conflict(item_id, start_datetime, end_datetime, period=start_period_num)
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
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
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


def create_image_thumbnail(image_path, thumbnail_path, size):
    """
    Create a thumbnail for an image file, always converting to JPG format.
    
    Args:
        image_path (str): Path to the original image
        thumbnail_path (str): Path where the thumbnail should be saved
        size (tuple): Thumbnail size as (width, height)
        
    Returns:
        bool: True if thumbnail was created successfully, False otherwise
    """
    try:
        with Image.open(image_path) as img:
            # Always convert to RGB for JPG output
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create thumbnail with proper aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Create a new image with the exact size (add padding if needed)
            thumb = Image.new('RGB', size, (255, 255, 255))
            
            # Calculate position to center the image
            x = (size[0] - img.size[0]) // 2
            y = (size[1] - img.size[1]) // 2
            
            thumb.paste(img, (x, y))
            
            # Ensure the thumbnail path ends with .jpg
            if not thumbnail_path.lower().endswith('.jpg'):
                thumbnail_path = os.path.splitext(thumbnail_path)[0] + '.jpg'
                
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


def generate_optimized_versions(filename, max_original_width=500, target_size_kb=80):
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
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Generate file paths
    name_part = os.path.splitext(filename)[0]
    converted_filename = f"{name_part}.jpg"
    converted_path = os.path.join(app.config['UPLOAD_FOLDER'], converted_filename)
    thumbnail_filename = f"{name_part}_thumb.jpg"
    preview_filename = f"{name_part}_preview.jpg"
    
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
    preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
    
    result = {
        'original': converted_filename,  # Use the JPG version as the original
        'thumbnail': None,
        'preview': None,
        'is_image': False,
        'is_video': False
    }
    
    if is_image_file(filename):
        result['is_image'] = True
        try:
            # Convert original to JPG if it's not already and resize/compress it
            with Image.open(original_path) as img:
                # Calculate new dimensions to maintain aspect ratio with max width of max_original_width
                original_width, original_height = img.size
                if original_width > max_original_width:
                    scaling_factor = max_original_width / original_width
                    new_width = max_original_width
                    new_height = int(original_height * scaling_factor)
                    # Resize with high quality resampling
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert to RGB for JPG output
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save as JPG with compression to target file size
                # Get optimal quality setting to reach target size
                quality = get_optimal_image_quality(img, target_size_kb=target_size_kb)
                img.save(converted_path, 'JPEG', quality=quality, optimize=True)
                
                # Remove the original non-JPG file or if it's been resized
                if not filename.lower().endswith('.jpg') or original_width > max_original_width:
                    try:
                        os.remove(original_path)
                    except Exception as e:
                        print(f"Error removing original file: {str(e)}")
                        
                original_path = converted_path  # Use the converted file for thumbnails
            
            # Create thumbnail
            if create_image_thumbnail(original_path, thumbnail_path, THUMBNAIL_SIZE):
                result['thumbnail'] = thumbnail_filename
            
            # Create preview
            if create_image_thumbnail(original_path, preview_path, PREVIEW_SIZE):
                result['preview'] = preview_filename
                
        except Exception as e:
            print(f"Error converting image to JPG: {str(e)}")
            return result
            
    elif is_video_file(filename):
        result['is_video'] = True
        # Create video thumbnail
        if create_video_thumbnail(original_path, thumbnail_path, THUMBNAIL_SIZE):
            result['thumbnail'] = thumbnail_filename
        
        # Create video preview
        if create_video_thumbnail(original_path, preview_path, PREVIEW_SIZE):
            result['preview'] = preview_filename
    
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
        db = client['Inventarsystem']
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
            
        # If we're within 10% of target, that's good enough
        if abs(size - target_size_bytes) < (target_size_bytes * 0.1):
            return quality
    
    return best_quality

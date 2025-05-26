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
from urllib.parse import urlparse, urlunparse
import requests
import os
import json
import datetime
import time
import traceback
import qrcode
from qrcode.constants import ERROR_CORRECT_L

# Set base directory for absolute path references
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'Hsse783942h2342f342342i34hwebf8'  # For production, use a secure key!
app.debug = False  # Debug disabled in production
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
QR_CODE_FOLDER = os.path.join(BASE_DIR, 'QRCodes')
app.config['QR_CODE_FOLDER'] = QR_CODE_FOLDER
app.config['STATIC_FOLDER'] = os.path.join(BASE_DIR, 'static')  # Explicitly set static folder

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
if not os.path.exists(app.config['QR_CODE_FOLDER']):
    os.makedirs(app.config['QR_CODE_FOLDER'])


def allowed_file(filename):
    """
    Check if a file has an allowed extension.
    
    Args:
        filename (str): Name of the file to check
        
    Returns:
        bool: True if the file extension is allowed, False otherwise
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


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
        flask.Response: The requested file
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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
        return {'item': item, 'status': 'success'}
    else:
        return {'error': 'Item not found', 'status': 'not_found'}, 404


@app.route('/upload_item', methods=['POST'])
def upload_item():
    """
    Route for adding new items to the inventory.
    Handles file uploads and creates QR codes.
    
    Returns:
        flask.Response: Redirect to admin homepage
    """
    # Authentication checks remain unchanged
    
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
    
    # Validation
    if not name or not ort or not beschreibung:
        flash('Bitte füllen Sie alle erforderlichen Felder aus', 'error')
        return redirect(url_for('home_admin'))

    # Only check for images if not duplicating and no duplicate images provided
    if not is_duplicating and not images and not duplicate_images:
        flash('Bitte laden Sie mindestens ein Bild hoch', 'error')
        return redirect(url_for('home_admin'))

    # Process any new uploaded images
    image_filenames = []
    for image in images:
        if image and image.filename and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            timestamp = time.strftime("%Y%m%d%H%M%S")
            saved_filename = f"{filename}_{timestamp}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
            image_filenames.append(saved_filename)
        elif image and image.filename:  # Only show error if there's an actual file
            flash('Ungültiges Dateiformat', 'error')
            return redirect(url_for('home_admin'))

    # Add the duplicate_images to the list
    if is_duplicating and duplicate_images:
        image_filenames.extend(duplicate_images)
        
    # Continue with existing code to create the item
    it.add_item(name, ort, beschreibung, image_filenames, filter_upload, 
                filter_upload2, filter_upload3, anschaffungs_jahr, 
                anschaffungs_kosten, code_4)
    flash('Objekt wurde erfolgreich hinzugefügt', 'success')
    
    # Get the item ID and create QR code
    item = it.get_item_by_name(name)
    if item:  # Check if item exists before trying to access its properties
        item_id = str(item['_id'])
        create_qr_code(item_id)
        # Pass the item ID to download the QR code
        return redirect(url_for('home_admin', new_item_id=item_id))
    else:
        # Handle case where item couldn't be retrieved
        flash('QR-Code konnte nicht erstellt werden. Bitte versuchen Sie es später erneut.', 'warning')
        return redirect(url_for('home_admin'))


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
    
    
    it.remove_item(id)
    flash('Item deleted successfully', 'success')
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
        if image and image.filename and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            images.append(filename)
    
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
    
    # Get number of exemplars to return (default to 1)
    exemplare_count = request.form.get('exemplare_count', 1)
    try:
        exemplare_count = int(exemplare_count)
        if exemplare_count < 1:
            exemplare_count = 1
    except (ValueError, TypeError):
        exemplare_count = 1
        
    # Get current exemplar status
    exemplare_status = item.get('ExemplareStatus', [])
    total_exemplare = item.get('Exemplare', 1)
    
    username = session['username']
    
    # If it's a simple item without exemplars
    if total_exemplare <= 1 or not exemplare_status:
        if not item.get('Verfuegbar', True) and (us.check_admin(session['username']) or item.get('User') == username):
            try:
                # Get existing borrowing record BEFORE updating the item status
                ausleihung_data = au.get_ausleihung_by_item(id)
                end_date = datetime.datetime.now()
                
                # Store the borrower's username before updating item status
                original_user = item.get('User', username)
                
                if ausleihung_data and '_id' in ausleihung_data:
                    # Update existing record
                    ausleihung_id = str(ausleihung_data['_id'])
                    user = ausleihung_data.get('User', original_user)
                    start = ausleihung_data.get('Start', datetime.datetime.now() - datetime.timedelta(hours=1))
                    
                    # Update the ausleihung first
                    au.update_ausleihung(ausleihung_id, id, user, start, end_date, status='completed')
                    
                    # Then update the item status (only once)
                    it.update_item_status(id, True, original_user)
                    flash('Item returned successfully', 'success')
                else:
                    # Fallback for missing record
                    it.update_item_status(id, True, original_user)
                    flash('Item returned successfully (new record created)', 'success')
            except Exception as e:
                it.update_item_status(id, True)
                flash(f'Item returned but encountered an error in record-keeping: {str(e)}', 'warning')
        else:
            flash('You are not authorized to return this item or it is already available', 'error')
    else:
        # Handle multi-exemplar item
        # Filter exemplars borrowed by current user
        user_exemplars = [ex for ex in exemplare_status if ex.get('user') == username]
        
        # Check if user has borrowed enough exemplars to return
        if len(user_exemplars) < exemplare_count:
            flash(f'You can only return up to {len(user_exemplars)} copies', 'error')
            exemplare_count = len(user_exemplars)
            
        if exemplare_count > 0:
            # Get the exemplars to return (limited to requested count)
            exemplars_to_return = user_exemplars[:exemplare_count]
            
            # Remove these exemplars from the status list
            updated_status = [ex for ex in exemplare_status if ex not in exemplars_to_return]
            
            # Update the item status
            it.update_item_exemplare_status(id, updated_status)
            
            # If all exemplars were borrowed but now some are available, update item status
            if not item.get('Verfuegbar', True) and len(updated_status) < total_exemplare:
                it.update_item_status(id, True)
            
            # Complete the ausleihungen for each returned exemplar
            end_date = datetime.datetime.now()
            for exemplar in exemplars_to_return:
                exemplar_id = f"{id}_{exemplar['number']}"
                ausleihung_data = au.get_ausleihung_by_item(exemplar_id, include_exemplar_id=True)
                
                if ausleihung_data and '_id' in ausleihung_data:
                    ausleihung_id = str(ausleihung_data['_id'])
                    start = ausleihung_data.get('Start', datetime.datetime.now() - datetime.timedelta(hours=1))
                    au.update_ausleihung(ausleihung_id, exemplar_id, username, start, end_date, status='completed')
            
            flash(f'{exemplare_count} copies returned successfully', 'success')
        else:
            flash('You have no copies to return', 'error')
    
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
        id (str): ID of the item
        
    Returns:
        dict: Borrowing details for the item
    """
    if 'username' not in session:
        return {'error': 'Not authorized', 'status': 'forbidden'}, 403
    
    # Get the borrowing record
    ausleihung = au.get_ausleihung_by_item(id, include_history=False)
    
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
    filename = f"{item['Name']}_{id}.png"
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
        flask.Response: Rendered template with logs or redirect
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
    Display items currently borrowed by the logged-in user.
    
    Returns:
        flask.Response: Rendered template of user's borrowed items
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    
    # Method 1: Get borrowed items directly from the items collection
    borrowed_items = []
    try:
        # Get all items borrowed by this user
        client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        db = client[MONGODB_DB]
        items_collection = db['items']
        
        # Find items borrowed by this user (single items)
        single_borrowed_items = list(items_collection.find({
            'Verfuegbar': False,
            'User': username
        }))
        
        # Find items with exemplar borrowings by this user
        multi_borrowed_items = list(items_collection.find({
            'ExemplareStatus': {
                '$elemMatch': {
                    'user': username
                }
            }
        }))
        
        # Process multi-exemplar items to extract only the exemplars borrowed by this user
        for item in multi_borrowed_items:
            item['_id'] = str(item['_id'])
            
            # Filter exemplars for only those borrowed by this user
            if 'ExemplareStatus' in item:
                user_exemplars = [ex for ex in item.get('ExemplareStatus', []) if ex.get('user') == username]
                item['UserExemplars'] = user_exemplars
                item['UserExemplarCount'] = len(user_exemplars)
        
        # Process single items
        for item in single_borrowed_items:
            item['_id'] = str(item['_id'])
        
        # Combine both types of borrowed items
        all_borrowed = single_borrowed_items + [item for item in multi_borrowed_items if item not in single_borrowed_items]
        
        # Sort by name
        all_borrowed.sort(key=lambda x: x.get('Name', '').lower())
        
        borrowed_items = all_borrowed
        client.close()
        
    except Exception as e:
        print(f"Error retrieving borrowed items: {e}")
        flash(f'Fehler beim Laden der ausgeliehenen Objekte: {str(e)}', 'error')
    
    return render_template('my_borrowed_items.html', 
                          items=borrowed_items, 
                          username=username)

@app.route('/favicon.ico')
def favicon():
    """
    Serve the favicon directly from the static directory.
    
    Returns:
        flask.Response: The favicon.ico file
    """
    return send_from_directory(app.config['STATIC_FOLDER'], 'favicon.ico')
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

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, get_flashed_messages
from werkzeug.utils import secure_filename
import user as us
import items as it
import ausleihung as au
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import json

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
    
except FileNotFoundError:
    print("Config file not found. Using default values.")
    # Default configuration
    __version__ = '1.2.4'
    app.debug = False
    app.secret_key = 'Hsse783942h2342f342342i34hwebf8'
    Host = '0.0.0.0'
    Port = 443
    
except json.JSONDecodeError:
    print("Error: Config file contains invalid JSON. Using default values.")
    # Default configuration
    __version__ = '1.2.4'
    app.debug = False
    app.secret_key = 'Hsse783942h2342f342342i34hwebf8'
    Host = '0.0.0.0'
    Port = 443

# Apply the configuration for general use throughout the app
APP_VERSION = __version__

@app.context_processor
def inject_version():
    """
    Makes the application version available to all templates
    """
    return {'version': APP_VERSION}

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
    
    # Filter items if needed
    if available_only:
        items = [item for item in items if item.get('Verfuegbar', False)]
    
    for item in items:
        item['Images'] = item.get('Images', [])
    
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
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    name = request.form['name']
    ort = request.form['ort']
    beschreibung = request.form['beschreibung']
    images = request.files.getlist('images')
    filter_upload = request.form.getlist('filter')
    filter_upload2 = request.form.getlist('filter2')
    filter_upload3 = request.form.getlist('filter3')
    anschaffungs_jahr = request.form.getlist('anschaffungsjahr')
    anschaffungs_kosten = request.form.getlist('anschaffungskosten')
    code_4 = request.form.getlist('code_4')
    
    if not name or not ort or not beschreibung or not images:
        flash('Please fill all fields', 'error')
        return redirect(url_for('home_admin'))

    image_filenames = []
    for image in images:
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filenames.append(filename)
        else:
            flash('Invalid file type', 'error')
            return redirect(url_for('home_admin'))

    it.add_item(name, ort, beschreibung, image_filenames, filter_upload, filter_upload2, filter_upload3, anschaffungs_jahr, anschaffungs_kosten, code_4)
    flash('Item uploaded successfully', 'success')
    
    # Get the item ID and create QR code
    item = it.get_item_by_name(name)
    item_id = str(item['_id'])
    create_qr_code(item_id)
    
    # Pass the item ID to download the QR code
    return redirect(url_for('home_admin', new_item_id=item_id))


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
    
    # Get form data
    name = request.form.get('name')
    ort = request.form.get('ort')
    beschreibung = request.form.get('beschreibung')
    filter1 = request.form.get('filter')
    filter2 = request.form.get('filter2')
    filter3 = request.form.get('filter3')
    anschaffungs_jahr = request.form.get('anschaffungsjahr')
    anschaffungs_kosten = request.form.get('anschaffungskosten')
    code_4 = request.form.get('code_4')
    
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
    if item and item['Verfuegbar']:
        it.update_item_status(id, False, session['username'])
        start_date = datetime.datetime.now()
        au.add_ausleihung(id, session['username'], start_date)

        flash('Item borrowed successfully', 'success')
    else:
        flash('Item is not available', 'error')
    
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
    if item and not item['Verfuegbar']:
        if not us.check_admin(session['username']) and item['User'] != session['username']:
            flash('You are not authorized to return this item', 'error')
            return redirect(url_for('home'))
        
        try:
            # Get existing borrowing record BEFORE updating the item status
            ausleihung_data = au.get_ausleihung_by_item(id)
            end_date = datetime.datetime.now()
            
            # Store the borrower's username before updating item status
            original_user = item.get('User', session['username'])
            
            if ausleihung_data and '_id' in ausleihung_data:
                # Update existing record
                ausleihung_id = str(ausleihung_data['_id'])
                user = ausleihung_data.get('User', original_user)
                start = ausleihung_data.get('Start', datetime.datetime.now() - datetime.timedelta(hours=1))
                
                # Update the ausleihung first
                au.update_ausleihung(ausleihung_id, id, user, start, end_date, status='completed')
                
                # Then update the item status (only once)
                return_it = it.update_item_status(id, True, original_user)
                flash('Item returned successfully', 'success')
            else:
                # Only create a new record if we absolutely can't find an existing one
                # This should rarely happen
                start_time = datetime.datetime.now() - datetime.timedelta(hours=1)
                
                # Update the item status first
                it.update_item_status(id, True, original_user)
                
                # Log a warning about missing record
                print(f"Warning: No borrowing record found for item {id} when returning. Creating new record.")
                
                # Create a historical record
                au.add_ausleihung(id, original_user, start_time, end_date, notes="Auto-generated return record", status="completed")
                flash('Item returned successfully (new record created)', 'success')
        except Exception as e:
            # If there's an error in record keeping, still make the item available
            it.update_item_status(id, True, user=original_user)
            flash('Item returned but encountered an error in record-keeping', 'warning')
            print(f"Error updating borrowing record: {e}")
    else:
        flash('Item is already available or does not exist', 'error')
    
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
    return it.get_filter()
    

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
    import qrcode
    from urllib.parse import urlparse, urlunparse
    
    if not os.path.exists(app.config['QR_CODE_FOLDER']):
        os.makedirs(app.config['QR_CODE_FOLDER'])
        
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
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
    img.save(qr_path)
    
    return filename


@app.route('/item/<id>')
def show_item(id):
    """
    Route to display a specific item.
    When accessing via QR code, this highlights the item in the UI.
    
    Args:
        id (str): ID of the item to display
        
    Returns:
        flask.Response: Rendered template with item highlighted
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
        
    item = it.get_item(id)
    if not item:
        flash('Item not found', 'error')
        if us.check_admin(session['username']):
            return redirect(url_for('home_admin'))
        return redirect(url_for('home'))
    
    # Pass the item ID to template to highlight it
    if us.check_admin(session['username']):
        return render_template('main_admin.html', highlight_item=str(id))
    return render_template('main.html', highlight_item=str(id))


@app.route('/user_status', methods=['GET'])
def user_status():
    """
    API endpoint to retrieve current user status.
    Used by frontend to adapt UI based on user role.
    
    Returns:
        dict: User status information including login state and admin status
    """
    if 'username' not in session:
        return {'logged_in': False}
    
    has_active = us.has_active_borrowing(session['username'])
    return {
        'logged_in': True,
        'username': session['username'],
        'is_admin': us.check_admin(session['username']),
        'has_active_borrowing': has_active
    }


@app.route('/admin/reset_item/<id>', methods=['POST'])
def admin_reset_item(id):
    """
    Admin route to reset an item's status.
    Used to fix stuck or problematic items.
    
    Args:
        id (str): ID of the item to reset
        
    Returns:
        flask.Response: Redirect to admin homepage
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    if not us.check_admin(session['username']):
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
    
    try:
        it.update_item_status(id, True)
        
        it.unstuck_item(id)
        
        flash('Item status has been reset successfully', 'success')
    except Exception as e:
        flash(f'Error resetting item: {e}', 'error')
    
    return redirect(url_for('home_admin'))


@app.route('/qr_code/<id>')
def get_qr_code(id):
    """
    Route to download the QR code for an item.
    
    Args:
        id (str): ID of the item to get QR code for
        
    Returns:
        flask.Response: QR code image file for download
    """
    item = it.get_item(id)
    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('home_admin'))
    
    filename = f"{item['Name']}_{id}.png"
    qr_path = os.path.join(app.config['QR_CODE_FOLDER'], filename)
    
    # If QR code doesn't exist yet, create it
    if not os.path.exists(qr_path):
        create_qr_code(id)
    
    return send_from_directory(app.config['QR_CODE_FOLDER'], filename, as_attachment=True)


@app.route('/license')
def license():
    """
    Route to display license information.
    
    Returns:
        flask.Response: Rendered license template
    """
    return render_template('license.html')


'''----------------------------------------------------------------------BOOKING ROUTES-----------------------------------------------------------------------------------------------------------------'''

@app.route('/get_bookings')
def get_bookings():
    """
    Get all bookings for calendar display
    """
    try:
        if 'username' not in session:
            flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
            return redirect(url_for('login'))
            
        start = request.args.get('start')
        end = request.args.get('end')
        
        print(f"Fetching bookings from {start} to {end}, requested by {session['username']}")
        
        bookings = []
        processed_items_with_status = set()  # Track item_id+status combinations instead of just items
        
        # Define school periods
        school_periods = {
            1: { 'start': '08:00', 'end': '08:45' },
            2: { 'start': '08:45', 'end': '09:30' },
            3: { 'start': '09:45', 'end': '10:30' },
            4: { 'start': '10:30', 'end': '11:15' },
            5: { 'start': '11:30', 'end': '12:15' },
            6: { 'start': '12:15', 'end': '13:00' },
            7: { 'start': '13:30', 'end': '14:15' },
            8: { 'start': '14:15', 'end': '15:00' },
            9: { 'start': '15:15', 'end': '16:00' },
            10: { 'start': '16:00', 'end': '16:45' }
        }
        
        # Helper function to determine period
        def get_period(time_obj):
            hours = time_obj.hour
            minutes = time_obj.minute
            time_str = f"{hours:02d}:{minutes:02d}"
            
            for period, times in school_periods.items():
                if times['start'] <= time_str <= times['end']:
                    return period
            return None
        
        try:
            # 1. Get PLANNED bookings first to ensure they appear
            planned_bookings = au.get_planned_bookings(start, end) or []
            print(f"Found {len(planned_bookings)} planned bookings")
            for booking in planned_bookings:
                item_id = booking.get('Item')
                
                item = it.get_item(item_id)
                if not item:
                    continue
                    
                # Format dates
                start_date = booking.get('Start')
                end_date = booking.get('End')
                
                # Determine period if not explicitly stored
                period = booking.get('Period')
                if not period and start_date:
                    period = get_period(start_date)
                
                # Convert to string safely
                start_str = start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date
                end_str = end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date
                
                # Track this item+status combination
                processed_items_with_status.add(f"{item_id}_planned")
                    
                bookings.append({
                    "id": str(booking.get('_id')),
                    "title": item.get('Name', 'Unknown Item'),
                    "start": start_str,
                    "end": end_str,
                    "itemId": item_id,
                    "userName": booking.get('User'),
                    "notes": booking.get('Notes', ''),
                    "status": "planned",
                    "period": period,
                    "isCurrentUser": booking.get('User') == session['username']
                })
            
            # 2. Get ACTIVE bookings 
            active_bookings = au.get_active_bookings(start, end) or []
            print(f"Found {len(active_bookings)} active bookings")
            for booking in active_bookings:
                item_id = booking.get('Item')
                
                # Skip if this item already has a planned booking (avoid duplicates)
                if f"{item_id}_planned" in processed_items_with_status:
                    continue
                    
                item = it.get_item(booking.get('Item'))
                if not item:
                    continue
                    
                # Format dates
                start_date = booking.get('Start') 
                end_date = booking.get('End')
                
                # Determine period if not explicitly stored
                period = booking.get('Period')
                if not period and start_date:
                    period = get_period(start_date)
                
                # Convert to string safely
                start_str = start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date
                end_str = end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date
                
                # Track this item+status combination
                processed_items_with_status.add(f"{item_id}_active")
                
                bookings.append({
                    "id": str(booking.get('_id')),
                    "title": item.get('Name', 'Unknown Item'),
                    "start": start_str,
                    "end": end_str,
                    "itemId": item_id,
                    "userName": booking.get('User'),
                    "notes": booking.get('Notes', ''),
                    "status": "current",
                    "period": period,
                    "isCurrentUser": booking.get('User') == session['username']
                })
            
            # 3. Get current borrowings from ausleihungen collection
            current_borrowings = au.get_ausleihungen(status='active', start=start, end=end) or []
            print(f"Found {len(current_borrowings)} current borrowings")
            
            # Format current borrowings for calendar
            for borrowing in current_borrowings:
                item_id = borrowing.get('Item')
                
                # Skip if this item already has an active or planned booking
                if (f"{item_id}_active" in processed_items_with_status or 
                    f"{item_id}_planned" in processed_items_with_status):
                    continue
                    
                item = it.get_item(item_id)
                if not item:
                    continue
                    
                # Format dates
                start_date = borrowing.get('Start')
                end_date = borrowing.get('End')
                
                # Determine period if not explicitly stored
                period = borrowing.get('Period')
                if not period and start_date:
                    period = get_period(start_date)
                
                # If end_date is None, set it to start_date + 1 hour
                if end_date is None:
                    end_date = start_date + datetime.timedelta(minutes=45)
                
                # Convert to string safely
                start_str = start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date
                end_str = end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date
                
                bookings.append({
                    "id": str(borrowing.get('_id')),
                    "title": item.get('Name', 'Unknown Item'),
                    "start": start_str,
                    "end": end_str,
                    "itemId": item_id,
                    "userName": borrowing.get('User'),
                    "notes": borrowing.get('Notes', ''),
                    "status": "current",
                    "period": period,
                    "isCurrentUser": borrowing.get('User') == session['username']
                })
            
            # 4. Add completed bookings
            completed_bookings = au.get_completed_bookings(start, end) or []
            print(f"Found {len(completed_bookings)} completed bookings")
            for booking in completed_bookings:
                item_id = booking.get('Item')
                item = it.get_item(item_id)
                if not item:
                    continue
                    
                # Format dates
                start_date = booking.get('Start')
                end_date = booking.get('End')
                
                # Determine period if not explicitly stored
                period = booking.get('Period')
                if not period and start_date:
                    period = get_period(start_date)
                
                # Convert to string safely
                start_str = start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date
                end_str = end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date
                    
                bookings.append({
                    "id": str(booking.get('_id')),
                    "title": item.get('Name', 'Unknown Item'),
                    "start": start_str,
                    "end": end_str,
                    "itemId": item_id,
                    "userName": booking.get('User'),
                    "notes": booking.get('Notes', ''),
                    "status": "completed",
                    "period": period,
                    "isCurrentUser": booking.get('User') == session['username']
                })
            
        except Exception as e:
            print(f"Error fetching specific booking type: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"Returning {len(bookings)} total bookings")
        return {"bookings": bookings}
    except Exception as e:
        import traceback
        print(f"Error in get_bookings: {e}")
        traceback.print_exc()
        return {"bookings": [], "error": str(e)}

@app.route('/plan_booking', methods=['POST'])
def plan_booking():
    """
    Create a new planned booking
    """
    if 'username' not in session:
        flash('Ihnen ist es nicht gestattet auf dieser Internetanwendung, die eben besuchte Adrrese zu nutzen, versuchen sie es erneut nach dem sie sich mit einem berechtigten Nutzer angemeldet haben!', 'error')
        return redirect(url_for('login'))
        
    # Extract form data with error handling
    try:
        item_id = request.form.get('item_id')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        period = request.form.get('period')
        notes = request.form.get('notes', '')
        
        # Log the booking attempt details
        print(f"Booking attempt: item={item_id}, period={period}")
        print(f"  - start_date_str={start_date_str}")
        print(f"  - end_date_str={end_date_str}")
        
        # Validate inputs
        if not all([item_id, start_date_str, end_date_str]):
            print("Missing required fields for booking")
            return {"success": False, "error": "Missing required fields"}, 400
            
        # Parse dates with detailed logging
        try:
            start_date = datetime.datetime.fromisoformat(start_date_str)
            end_date = datetime.datetime.fromisoformat(end_date_str)
            print(f"Parsed dates: start={start_date}, end={end_date}")
        except ValueError as e:
            print(f"Date parsing error: {e}")
            return {"success": False, "error": f"Invalid date format: {e}"}, 400
            
        # Check if item exists
        item = it.get_item(item_id)
        if not item:
            print(f"Item {item_id} not found")
            return {"success": False, "error": "Item not found"}, 404
            
        # Check for date conflicts
        print(f"Checking conflicts for item {item_id} on {start_date}")
        if au.check_booking_conflict(item_id, start_date, end_date, period):
            print(f"Conflict detected for item {item_id}, period {period}")
            return {"success": False, "error": "Objekt ist in diesem Zeitraum bereits gebucht"}, 409
        
        # Create the planned booking with period information
        print(f"Creating booking for item {item_id}, period {period}")
        booking_id = au.add_planned_booking(
            item_id, 
            session['username'], 
            start_date, 
            end_date, 
            notes, 
            period=period
        )
        
        if not booking_id:
            print("Failed to create booking - null booking ID returned")
            return {"success": False, "error": "Fehler beim Erstellen der Reservierung"}, 500
        
        print(f"Successfully created booking {booking_id}")
        return {"success": True, "booking_id": str(booking_id)}
        
    except Exception as e:
        import traceback
        print(f"Error in plan_booking: {e}")
        traceback.print_exc()
        return {"success": False, "error": f"Server error: {str(e)}"}, 500

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
            
        return render_template('terminplan.html')
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
        return us.get_users()
    else:
        flash('Please login to access this function', 'error')

'''-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------'''

scheduler = BackgroundScheduler()

def process_bookings():
    """
    Check for bookings that should start now and process them
    """
    # Create a proper datetime object
    current_time = datetime.datetime.now()
    
    # Define school periods
    school_periods = {
        1: { 'start': '08:00', 'end': '08:45' },
        2: { 'start': '08:45', 'end': '09:30' },
        3: { 'start': '09:45', 'end': '10:30' },
        4: { 'start': '10:30', 'end': '11:15' },
        5: { 'start': '11:30', 'end': '12:15' },
        6: { 'start': '12:15', 'end': '13:00' },
        7: { 'start': '13:30', 'end': '14:15' },
        8: { 'start': '14:15', 'end': '15:00' },
        9: { 'start': '15:15', 'end': '16:00' },
        10: { 'start': '16:00', 'end': '16:45' }
    }
    
    # Get current hour and minute
    current_hour = current_time.hour
    current_minute = current_time.minute
    current_time_str = f"{current_hour:02d}:{current_minute:02d}"
    
    # Determine if we're currently in a school period
    current_period = None
    for period, times in school_periods.items():
        if times['start'] <= current_time_str <= times['end']:
            current_period = period
            break
    
    # Pass the datetime object to the function
    bookings = au.get_bookings_starting_now(current_time)
    
    # Process the bookings
    for booking in bookings:
        try:
            booking_id = str(booking.get('_id'))
            item_id = booking.get('Item')
            user = booking.get('User')
            start_date = booking.get('Start')
            end_date = booking.get('End')
            notes = booking.get('Notes', '')
            period = booking.get('Period')
            
            # Only activate bookings if we're in the right period or within the booking time window
            booking_period = period
            should_activate = False
            
            if booking_period and booking_period == current_period:
                # We're in the exact period, so activate
                should_activate = True
            elif start_date <= current_time <= end_date:
                # We're within the exact booking time window
                should_activate = True
                
            if not should_activate:
                continue
                
            # Check if an ausleihung record already exists for this booking
            existing_ausleihung = au.get_ausleihung_by_item(item_id, status='active')
            
            if existing_ausleihung:
                # Just mark the booking as active and link to existing ausleihung
                au.mark_booking_active(booking_id, str(existing_ausleihung.get('_id')))
                print(f"Booking {booking_id} linked to existing ausleihung {existing_ausleihung.get('_id')}")
            else:
                # No existing ausleihung, create a new one
                ausleihung_id = au.add_ausleihung(
                    item_id,
                    user,
                    start_date,
                    end_date,
                    notes,
                    period=period
                )
                
                if ausleihung_id:
                    # Mark the booking as active and link it to the ausleihung
                    au.mark_booking_active(booking_id, str(ausleihung_id))
                    
                    # Update item status
                    it.update_item_status(item_id, False, user)
                    print(f"Created new ausleihung {ausleihung_id} for booking {booking_id}")
                else:
                    print(f"Failed to create ausleihung for booking {booking_id}")
        except Exception as e:
            print(f"Error processing booking: {e}")
    
    # Also check for bookings that should end now
    ending_bookings = au.get_bookings_ending_now(current_time)
    
    for booking in ending_bookings:
        try:
            booking_id = str(booking.get('_id'))
            item_id = booking.get('Item')
            ausleihung_id = booking.get('AusleihungId')
            period = booking.get('Period')
            
            # Only end bookings if we're out of the period or past the end time
            should_end = False
            
            if period and period == current_period:
                # If we're at the end of the period (within 5 minutes of the end)
                period_end = school_periods.get(period, {}).get('end', '')
                if period_end:
                    period_end_hour, period_end_minute = map(int, period_end.split(':'))
                    if current_hour == period_end_hour and abs(current_minute - period_end_minute) <= 5:
                        should_end = True
            elif end_date and current_time >= end_date:
                # We're past the end time
                should_end = True
                
            if not should_end:
                continue
            
            # Mark item as available again
            it.update_item_status(item_id, True)
            
            # Update booking status to completed
            au.mark_booking_completed(booking_id)
            
            # Update the ausleihung record to set end date if it exists
            if ausleihung_id:
                # Get the ausleihung record
                ausleihung = au.get_ausleihung(ausleihung_id)
                if ausleihung:
                    # Update with end date
                    au.update_ausleihung(
                        ausleihung_id,
                        item_id,
                        ausleihung.get('User'),
                        ausleihung.get('Start'),
                        current_time
                    )
        except Exception as e:
            print(f"Error ending booking: {e}")
            
scheduler.add_job(process_bookings, 'interval', minutes=1)
scheduler.start()

if __name__ == '__main__':
    """
    Development server execution.
    This block only runs when executing app.py directly, not when using Gunicorn.
    Includes SSL configuration for secure development testing.
    """
    # SSL configuration
    ssl_context = ('ssl_certs/cert.pem', 'ssl_certs/key.pem')
    app.run(Host, Port, ssl_context=ssl_context)

import atexit
atexit.register(lambda: scheduler.shutdown())
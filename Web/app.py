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
"""

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, get_flashed_messages
from werkzeug.utils import secure_filename
from database import User as us
from database import Inventory as it
from database import ausleihung as au
from bson.objectid import ObjectId
import hashlib
import datetime

# Set base directory for absolute path references
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'secret'  # For production, use a secure key!
app.debug = False  # Debug disabled in production
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
QR_CODE_FOLDER = os.path.join(BASE_DIR, 'QRCodes')
app.config['QR_CODE_FOLDER'] = QR_CODE_FOLDER
__version__ = '0.0.1'

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
    if 'username' in session and not us.check_admin(session['username']):
        return render_template('main.html', username=session['username'])
    elif 'username' in session and us.check_admin(session['username']):
        return redirect(url_for('home_admin'))
    return redirect(url_for('logout'))


@app.route('/home_admin')
def home_admin():
    """
    Admin homepage route.
    Only accessible by users with admin privileges.
    
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' in session:
        if not us.check_admin(session['username']):
            flash('You are not authorized to view this page', 'error')
            return redirect(url_for('logout'))
        return render_template('main_admin.html', username=session['username'])
    
    return redirect(url_for('logout'))


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
        
        user_instance = us()
        user = user_instance.check_nm_pwd(username, password)

        if user:
            session['username'] = username
            if user['Admin']:
                return redirect(url_for('home_admin'))
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'error')
            get_flashed_messages()
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration route.
    Creates new user accounts (admin access required).
    
    Returns:
        flask.Response: Rendered template or redirect
    """
    if 'username' not in session or not us.check_admin(session['username']):
        return redirect(url_for('login'))
    elif 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Please fill all fields', 'error')
            Flask.get_flash_messages()
            return redirect(url_for('register'))
        if us.get_user(username):
            flash('User already exists', 'error')
            return redirect(url_for('register'))
        if not us.check_password_strength(password):
            flash('Password is too weak', 'error')
            return redirect(url_for('register'))
        us.add_user(username, password)
        session['username'] = username
        return redirect(url_for('home'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    """
    User logout route.
    Removes user session data and redirects to login.
    
    Returns:
        flask.Response: Redirect to login page
    """
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/get_items', methods=['GET'])
def get_items():
    """
    API endpoint to retrieve all inventory items.
    
    Returns:
        dict: Dictionary containing all inventory items
    """
    items = it.get_items()
    for item in items:
        item['Images'] = item.get('Images', [])
    return {'items': items}


@app.route('/upload_item', methods=['POST'])
def upload_item():
    """
    Route for adding new items to the inventory.
    Handles file uploads and creates QR codes.
    
    Returns:
        flask.Response: Redirect to admin homepage
    """
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to upload items', 'error')
        return redirect(url_for('home'))
    
    name = request.form['name']
    ort = request.form['ort']
    beschreibung = request.form['beschreibung']
    images = request.files.getlist('images')
    filter_upload = request.form.getlist('filter')
    filter_upload2 = request.form.getlist('filter2')
    
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

    it.add_item(name, ort, beschreibung, image_filenames, filter_upload, filter_upload2)
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
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to delete items', 'error')
        return redirect(url_for('home'))
    
    it.remove_item(id)
    flash('Item deleted successfully', 'success')
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
        flash('You need to be logged in to borrow items', 'error')
        return redirect(url_for('login'))
    
    item = it.get_item(id)
    if item and item['Verfuegbar']:
        it.update_item_status(id, False)
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
        flash('You need to be logged in to return items', 'error')
        return redirect(url_for('login'))
    
    item = it.get_item(id)
    if item and not item['Verfuegbar']:
        it.update_item_status(id, True)
        
        try:
            # Get existing borrowing record
            ausleihung_data = au.get_ausleihung_by_item(id)
            
            end_date = datetime.datetime.now()
            
            if ausleihung_data and '_id' in ausleihung_data:
                # Update existing record
                ausleihung_id = str(ausleihung_data['_id'])
                user = ausleihung_data.get('User', session['username'])
                start = ausleihung_data.get('Start', datetime.datetime.now() - datetime.timedelta(hours=1))
                
                update_result = au.update_ausleihung(ausleihung_id, id, user, start, end_date)
                flash('Item returned successfully', 'success')
            else:
                # Create new record with default values
                start_time = datetime.datetime.now() - datetime.timedelta(hours=1)
                au.add_ausleihung(id, session['username'], start_time, end_date)
                flash('Item returned successfully (new record created)', 'success')
        except Exception as e:
            flash('Item returned but encountered an error in record-keeping', 'warning')
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
    if not os.path.exists(app.config['QR_CODE_FOLDER']):
        os.makedirs(app.config['QR_CODE_FOLDER'])
        
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Get base URL from request
    base_url = request.url_root
    if base_url.startswith('http:'):
        base_url = base_url.replace('http:', 'https:')
    
    # URL that will open this item directly
    qr.add_data(f"{base_url}item/{id}")
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
    if 'username' not in session or not us.check_admin(session['username']):
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))
    
    try:
        # Force the item to be available
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


if __name__ == '__main__':
    """
    Development server execution.
    This block only runs when executing app.py directly, not when using Gunicorn.
    Includes SSL configuration for secure development testing.
    """
    # SSL configuration
    ssl_context = ('ssl_certs/cert.pem', 'ssl_certs/key.pem')
    app.run("0.0.0.0", 8000, ssl_context=ssl_context)
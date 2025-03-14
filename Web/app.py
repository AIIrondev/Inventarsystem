import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, get_flashed_messages
from werkzeug.utils import secure_filename
from database import User as us
from database import Inventory as it
from database import ausleihung as au
from bson.objectid import ObjectId
import hashlib
import datetime


app = Flask(__name__)
app.secret_key = 'secret'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
__version__ = '0.0.1'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/test_connection', methods=['GET'])
def test_connection():
    return {'status': 'success', 'message': 'Connection successful', 'version': __version__, 'status_code': 200}

@app.route('/')
def home():
    if 'username' in session and not us.check_admin(session['username']):
        return render_template('main.html', username=session['username'])
    elif 'username' in session and us.check_admin(session['username']):
        return redirect(url_for('home_admin'))
    return redirect(url_for('logout'))

@app.route('/home_admin')
def home_admin():
    if 'username' in session:
        if not us.check_admin(session['username']):
            flash('You are not authorized to view this page', 'error')
            return redirect(url_for('logout'))
        return render_template('main_admin.html', username=session['username'])
    
    return redirect(url_for('logout'))

@app.route('/login', methods=['GET', 'POST'])
def login():
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
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/get_items', methods=['GET'])
def get_items():
    items = it.get_items()
    for item in items:
        item['Images'] = item.get('Images', [])
    return {'items': items}

@app.route('/upload_item', methods=['POST'])
def upload_item():
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
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to delete items', 'error')
        return redirect(url_for('home'))
    
    it.remove_item(id)
    flash('Item deleted successfully', 'success')
    return redirect(url_for('home_admin'))

@app.route('/get_ausleihungen', methods=['GET'])
def get_ausleihungen():
    ausleihungen = au.get_ausleihungen()
    return {'ausleihungen': ausleihungen}

@app.route('/ausleihen/<id>', methods=['POST'])
def ausleihen(id):
    if 'username' not in session:
        flash('You need to be logged in to borrow items', 'error')
        return redirect(url_for('login'))
    
    # Debug output
    print(f"User {session['username']} attempting to borrow item {id}")
    
    # Check if user already has an active borrowing
    has_active = us.has_active_borrowing(session['username'])
    print(f"Has active borrowing result: {has_active}")
    
    if has_active:
        flash('You already have an item borrowed. Please return it before borrowing another one.', 'error')
        if us.check_admin(session['username']):
            return redirect(url_for('home_admin'))
        return redirect(url_for('home'))
    
    item = it.get_item(id)
    if item and item['Verfuegbar']:
        it.update_item_status(id, False)
        au.add_ausleihung(id, session['username'], datetime.datetime.now())
        # Mark user as having an active borrowing
        us.update_active_borrowing(session['username'], id, True)
        flash('Item borrowed successfully', 'success')
    else:
        flash('Item is not available', 'error')
    
    if 'username' in session and not us.check_admin(session['username']):
        return redirect(url_for('home'))
    return redirect(url_for('home_admin'))

@app.route('/zurueckgeben/<id>', methods=['POST'])
def zurueckgeben(id):
    if 'username' not in session:
        flash('You need to be logged in to return items', 'error')
        return redirect(url_for('logout'))
    
    # Add debug output
    print(f"User {session['username']} attempting to return item {id}")
    
    item = it.get_item(id)
    if item and not item['Verfuegbar']:
        it.update_item_status(id, True)
        
        try:
            # Get the borrowing record
            ausleihung_data = au.get_ausleihung_by_item(id)
            print(f"Ausleihung data retrieved: {ausleihung_data}")
            
            if ausleihung_data:
                # Handle different data formats
                if isinstance(ausleihung_data, tuple) and len(ausleihung_data) == 4:
                    # Original expected format
                    _id, user, start, end = ausleihung_data
                elif isinstance(ausleihung_data, dict):
                    # Dictionary format
                    _id = str(ausleihung_data.get('_id'))
                    user = ausleihung_data.get('User', session['username'])
                    start = ausleihung_data.get('Start', datetime.datetime.now())
                    end = datetime.datetime.now()
                else:
                    # Other format - use what we can
                    _id = str(id)  # Use the item ID as fallback
                    user = session['username']
                    start = datetime.datetime.now() - datetime.timedelta(hours=1)  # Assume borrowed 1 hour ago
                    end = datetime.datetime.now()
                
                # Update the ausleihung record
                update_result = au.update_ausleihung(_id, id, session['username'], start, end)
                print(f"Update ausleihung result: {update_result}")
                
                # Clear the user's active borrowing status
                us.update_active_borrowing(session['username'], None, False)
                flash('Item returned successfully', 'success')
            else:
                # Create a new return record if one doesn't exist
                print("No ausleihung record found, creating a new one")
                au.add_ausleihung(id, session['username'], 
                                  datetime.datetime.now() - datetime.timedelta(hours=1),
                                  datetime.datetime.now())
                us.update_active_borrowing(session['username'], None, False)
                flash('Item returned successfully', 'success')
        except Exception as e:
            print(f"Error in zurueckgeben: {e}")
            # Force the item to be available and reset user borrowing status
            it.update_item_status(id, True)
            us.update_active_borrowing(session['username'], None, False)
            flash('Item returned but encountered an error in record-keeping', 'warning')
    else:
        flash('Item is already available', 'error')
    
    if 'username' in session and not us.check_admin(session['username']):
        return redirect(url_for('home'))
    return redirect(url_for('home_admin'))

@app.route('/get_filter', methods=['GET'])
def get_filter():
    return it.get_filter()
    
def create_qr_code(id):
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

QR_CODE_FOLDER = 'QRCodes'
app.config['QR_CODE_FOLDER'] = QR_CODE_FOLDER

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['QR_CODE_FOLDER']):
        os.makedirs(app.config['QR_CODE_FOLDER'])
    
    # SSL configuration
    ssl_context = ('ssl_certs/cert.pem', 'ssl_certs/key.pem')
    app.run("0.0.0.0", 8000, debug=True, ssl_context=ssl_context)
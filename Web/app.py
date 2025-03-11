import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, get_flashed_messages
from werkzeug.utils import secure_filename
from database import User as us
from database import Inventory as it
from database import ausleihung as au
from bson.objectid import ObjectId
import hashlib
import datetime
from tkinter import messagebox


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
    return redirect(url_for('login'))

@app.route('/home_admin')
def home_admin():
    if 'username' in session:
        if not us.check_admin(session['username']):
            flash('You are not authorized to view this page', 'error')
            return redirect(url_for('login'))
        return render_template('main_admin.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
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
        return redirect(url_for('login'))
    
    name = request.form['name']
    ort = request.form['ort']
    beschreibung = request.form['beschreibung']
    images = request.files.getlist('images')

    image_filenames = []
    for image in images:
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filenames.append(filename)
        else:
            flash('Invalid file type', 'error')
            return redirect(url_for('home_admin'))

    it.add_item(name, ort, beschreibung, image_filenames)
    flash('Item uploaded successfully', 'success')
    
    return redirect(url_for('home_admin'))

@app.route('/delete_item/<id>', methods=['POST', 'GET'])
def delete_item(id):
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to delete items', 'error')
        return redirect(url_for('login'))
    
    it.remove_item(id)
    flash('Item deleted successfully', 'success')
    return redirect(url_for('home_admin'))

@app.route('/get_ausleihungen', methods=['GET'])
def get_ausleihungen():
    ausleihungen = au.get_ausleihungen()
    return {'ausleihungen': ausleihungen}

@app.route('/ausleihen/<id>', methods=['GET', 'POST'])
def ausleihen(id):
    if 'username' not in session:
        flash('You are not authorized to view this page', 'error')
        return redirect(url_for('login'))
    item = it.get_item(id)
    try :
        ausleihung = au.get_ausleihung_by_item(id)
        _id, user, start, end = ausleihung
    except:
        ausleihung = None
    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('home'))
    if item['Verfügbar'] == False:
        if ausleihung and user == session['username']:
            it.update_item_status(id, True)
            au.update_ausleihung(_id, id, session['username'], start, datetime.datetime.now())
            us.update_active_ausleihung(session['username'], id, False)
            flash('Item returned successfully', 'success')
            return redirect(url_for('home'))
        flash('Item already borrowed', 'error')
        return redirect(url_for('home'))
    it.update_item_status(id, False)
    au.add_ausleihung(id, session['username'], datetime.datetime.now())
    us.update_active_ausleihung(session['username'], id, True)
    flash('Item borrowed successfully', 'success')
    return redirect(url_for('home'))


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run("0.0.0.0", 8000)
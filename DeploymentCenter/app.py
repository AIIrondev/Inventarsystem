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
__version__ = '1.0.0'


@app.route('/test_connection', methods=['GET'])
def test_connection():
    return {'status': 'success', 'message': 'Connection successful', 'version': __version__, 'status_code': 200}

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('main.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Please fill all fields', 'error')
            get_flashed_messages()
            return redirect(url_for('login'))
        
        user_instance = us()
        user = user_instance.check_nm_pwd(username, password)

        return render_template('main.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

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

@app.route('/delete_user', methods=['GET', 'POST'])
def delete_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Please fill all fields', 'error')
            return redirect(url_for('delete_user'))
        user_instance = us()
        user = user_instance.check_nm_pwd(username, password)
        if not user:
            flash('Invalid credentials', 'error')
            return redirect(url_for('delete_user'))
        user_instance.delete_user(username)
        session.pop('username', None)
        return redirect(url_for('login'))
    return render_template('delete_user.html')

@app.route('/logs', methods=['GET'])
def logs():
    if not session.get('username'):
        return redirect(url_for('login'))
    return render_template('logs.html')

@app.route('/start_website', methods=['POST', 'GET'])
def start_website():
    if not session.get('username'):
        return redirect(url_for('login'))
    # start the website with the .sh file
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
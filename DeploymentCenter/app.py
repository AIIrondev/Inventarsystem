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
    if 'username' in session and us.check_admin(session['username']):
        return render_template('main.html')
    flash('You are not authorized to view this page', 'error')
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
                return redirect(url_for('home'))
            flash("You dont have a valid Permision to enter.")
            return redirect(url_for('login'))
        else:
            flash('Invalid credentials', 'error')

        flash('Invalid credentials', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
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
    return render_template('user_del.html')

@app.route('/delete_user', methods=['POST'])
def delete_user():
    username = request.form['username']
    id = us.get_user(username)
    if 'username' in session and us.check_admin(session['username']):
        us.delete_user(id)
        return redirect(url_for('home'))
    flash('You are not authorized to view this page', 'error')
    return redirect(url_for('login'))

@app.route('/logs', methods=['GET'])
def logs():
    if not session.get('username'):
        return redirect(url_for('login'))
    return render_template('logs.html')

@app.route('/get_logs', methods=['GET'])
def get_logs():
    if not session.get('username'):
        return redirect(url_for('login'))
    logs = au.get_ausleihungen()
    return logs

@app.route('/start_website', methods=['POST', 'GET'])
def start_website():
    if not session.get('username'):
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route('/get_usernames', methods=['GET'])
def get_usernames():
    if 'username' in session and not us.check_admin(session['username']):
        flash('You are not authorised to use this page', 'error')
        return redirect(url_for('logout'))
    elif 'username' in session and us.check_admin(session['username']):
        return us.get_users()
    else:
        flash('Please login to access this function', 'error')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
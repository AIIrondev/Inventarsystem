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
    if 'username' in session and us.check_admin(session['username']):
        # Get all users except the current one (to prevent self-deletion)
        all_users = us.get_all_users()
        # Format them as needed for the template
        users_list = []
        for user in all_users:
            if user['username'] != session['username']:  # Prevent self-deletion
                users_list.append({
                    'username': user['username'],
                    'admin': user.get('Admin', False)
                })
        return render_template('user_del.html', users=users_list)
    else:
        flash('You are not authorized to view this page', 'error')
        return redirect(url_for('login'))

@app.route('/delete_user', methods=['POST'])
def delete_user():
    username = request.form['username']
    id = us.get_user(username)
    if 'username' in session and us.check_admin(session['username']):
        us.delete_user(id)
        return redirect(url_for('home'))
    flash('You are not authorized to view this page', 'error')
    return redirect(url_for('login'))

@app.route('/logs')
def logs():
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to view this page', 'error')
        return redirect(url_for('login'))
        
    # Get ausleihungen
    all_ausleihungen = au.get_ausleihungen()
    print(f"Retrieved {len(all_ausleihungen)} ausleihungen")
    
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
            print(f"Error processing ausleihung {ausleihung.get('_id')}: {e}")
            continue
    
    return render_template('logs.html', items=formatted_items)

@app.route('/get_logs', methods=['GET'])
def get_logs():
    if not session.get('username'):
        return redirect(url_for('login'))
    logs = au.get_ausleihungen()
    return logs

@app.route('/restart_website', methods=['POST'])
def restart_website():
    if 'username' in session and us.check_admin(session['username']):
        os.system('sudo systemctl restart apache2')
        return redirect(url_for('home'))
    flash('You are not authorized to view this page', 'error')
    return redirect(url_for('login'))

@app.route('/get_usernames', methods=['GET'])
def get_usernames():
    if 'username' in session and not us.check_admin(session['username']):
        flash('You are not authorised to use this page', 'error')
        return redirect(url_for('logout'))
    elif 'username' in session and us.check_admin(session['username']):
        return us.get_users()
    else:
        flash('Please login to access this function', 'error')

@app.route('/debug_db')
def debug_db():
    if 'username' in session and us.check_admin(session['username']):
        result = {}
        try:
            from pymongo import MongoClient
            client = MongoClient('localhost', 27017)
            
            # Check both potential database names
            dbs = ['Inventarsystem', 'inventarsystem']
            for db_name in dbs:
                db = client[db_name]
                collections = db.list_collection_names()
                result[db_name] = {}
                for collection in collections:
                    count = db[collection].count_documents({})
                    result[db_name][collection] = count
                    
                    # If this is ausleihungen, show a sample document
                    if collection == 'ausleihungen' and count > 0:
                        sample = db[collection].find_one()
                        result[db_name]['ausleihungen_sample'] = str(sample)
            
            client.close()
            return render_template('debug.html', result=result)
        except Exception as e:
            return f"Error: {str(e)}"
    else:
        return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
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
Inventarsystem Management Application

This application provides administrative tools for managing the Inventarsystem:
- User management (creation, deletion)
- System logs viewing
- Borrowing history
- System administration functions

This is a separate application from the main Inventarsystem and is designed for
administrative use only. It provides tools that should not be accessible to
regular users of the system.
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

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'secret'  # Should use a secure key in production
__version__ = '1.0.0'


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
    Main route for the management application homepage.
    Only accessible to administrators.
    
    Returns:
        flask.Response: Rendered template or redirect to login
    """
    if 'username' in session and us.check_admin(session['username']):
        return render_template('main.html')
    flash('You are not authorized to view this page', 'error')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login route for administrators.
    Validates credentials and restricts access to admin users only.
    
    Returns:
        flask.Response: Rendered template or redirect based on credentials
    """
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
    """
    User logout route.
    Removes user session data and redirects to login.
    
    Returns:
        flask.Response: Redirect to login page
    """
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration route.
    Creates new user accounts (admin access required).
    
    Returns:
        flask.Response: Rendered template or redirect
    """
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
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to view this page', 'error')
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
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to perform this action', 'error')
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
    if 'username' not in session or not us.check_admin(session['username']):
        flash('You are not authorized to view this page', 'error')
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


@app.route('/restart_website', methods=['POST'])
def restart_website():
    """
    System administration function to restart the web server.
    Requires administrator privileges.
    
    Returns:
        flask.Response: Redirect to homepage on success or login on failure
    """
    if 'username' in session and us.check_admin(session['username']):
        os.system('sudo systemctl restart apache2')
        return redirect(url_for('home'))
    flash('You are not authorized to view this page', 'error')
    return redirect(url_for('login'))


@app.route('/get_usernames', methods=['GET'])
def get_usernames():
    """
    API endpoint to retrieve all usernames from the system.
    Requires administrator privileges.
    
    Returns:
        dict: Dictionary containing all users or redirect if not authenticated
    """
    if 'username' in session and not us.check_admin(session['username']):
        flash('You are not authorised to use this page', 'error')
        return redirect(url_for('logout'))
    elif 'username' in session and us.check_admin(session['username']):
        return us.get_users()
    else:
        flash('Please login to access this function', 'error')


if __name__ == "__main__":
    """
    Development server execution block.
    This code only runs when the script is executed directly, not when imported.
    """
    app.run(host="0.0.0.0", port=5000)
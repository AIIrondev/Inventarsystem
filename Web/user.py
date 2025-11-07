"""
Module for managing user accounts and authentication.
Provides methods for creating, validating, and retrieving user information.
"""
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
from pymongo import MongoClient
import hashlib
from bson.objectid import ObjectId


# === FAVORITES MANAGEMENT ===
def get_favorites(username):
    """Return a list of favorite item ObjectId strings for the user."""
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    user = users.find_one({'Username': username}) or users.find_one({'username': username})
    client.close()
    if not user:
        return []
    favs = user.get('favorites', [])
    # Normalize to strings
    return [str(f) for f in favs if f]

def add_favorite(username, item_id):
    """Add an item to user's favorites (idempotent)."""
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        users.update_one(
            {'$or': [{'Username': username}, {'username': username}]},
            {'$addToSet': {'favorites': ObjectId(item_id)}}
        )
        client.close()
        return True
    except Exception:
        return False

def remove_favorite(username, item_id):
    """Remove an item from user's favorites."""
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        users.update_one(
            {'$or': [{'Username': username}, {'username': username}]},
            {'$pull': {'favorites': ObjectId(item_id)}}
        )
        client.close()
        return True
    except Exception:
        return False



def check_password_strength(password):
    """
    Check if a password meets minimum security requirements.
    
    Args:
        password (str): Password to check
        
    Returns:
        bool: True if password is strong enough, False otherwise
    """
    if len(password) < 6:
        return False
    return True


def hashing(password):
    """
    Hash a password using SHA-512.
    
    Args:
        password (str): Password to hash
        
    Returns:
        str: Hexadecimal digest of the hashed password
    """
    return hashlib.sha512(password.encode()).hexdigest()


def check_nm_pwd(username, password):
    """
    Verify username and password combination.
    
    Args:
        username (str): Username to check
        password (str): Password to verify
        
    Returns:
        dict: User document if credentials are valid, None otherwise
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    hashed_password = hashlib.sha512(password.encode()).hexdigest()
    user = users.find_one({'Username': username, 'Password': hashed_password})
    client.close()
    return user


def add_user(username, password, name, last_name):
    """
    Add a new user to the database.
    
    Args:
        username (str): Username for the new user
        password (str): Password for the new user
        
    Returns:
        bool: True if user was added successfully, False if password was too weak
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    if not check_password_strength(password):
        return False
    users.insert_one({'Username': username, 'Password': hashing(password), 'Admin': False, 'active_ausleihung': None, 'name': name, 'last_name': last_name})
    client.close()
    return True


def make_admin(username):
    """
    Grant administrator privileges to a user.
    
    Args:
        username (str): Username of the user to promote
        
    Returns:
        bool: True if user was promoted successfully
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    users.update_one({'Username': username}, {'$set': {'Admin': True}})
    client.close()
    return True

def remove_admin(username):
    """
    Remove administrator privileges from a user.
    
    Args:
        username (str): Username of the user to demote
        
    Returns:
        bool: True if user was demoted successfully
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    users.update_one({'Username': username}, {'$set': {'Admin': False}})
    client.close()
    return True

def get_user(username):
    """
    Retrieve a specific user by username.
    
    Args:
        username (str): Username to search for
        
    Returns:
        dict: User document or None if not found
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    users_return = users.find_one({'Username': username})
    client.close()
    return users_return


def check_admin(username):
    """
    Check if a user has administrator privileges.
    
    Args:
        username (str): Username to check
        
    Returns:
        bool: True if user is an administrator, False otherwise
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    user = users.find_one({'Username': username})
    client.close()
    return user and user.get('Admin', False)


def update_active_ausleihung(username, id_item, ausleihung):
    """
    Update a user's active borrowing record.
    
    Args:
        username (str): Username of the user
        id_item (str): ID of the borrowed item
        ausleihung (str): ID of the borrowing record
        
    Returns:
        bool: True if successful
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    users.update_one({'Username': username}, {'$set': {'active_ausleihung': {'Item': id_item, 'Ausleihung': ausleihung}}})
    client.close()
    return True


def get_active_ausleihung(username):
    """
    Get a user's active borrowing record.
    
    Args:
        username (str): Username of the user
        
    Returns:
        dict: Active borrowing information or None
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    user = users.find_one({'Username': username})
    return user['active_ausleihung']


def has_active_borrowing(username):
    """
    Check if a user currently has an active borrowing.
    
    Args:
        username (str): Username to check
        
    Returns:
        bool: True if user has an active borrowing, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        
        user = users.find_one({'username': username})
        if not user:
            user = users.find_one({'Username': username})
            
        if not user:
            client.close()
            return False
            
        has_active = user.get('active_borrowing', False)
        
        client.close()
        return has_active
    except Exception as e:
        return False


def delete_user(username):
    """
    Delete a user from the database.
    Administrative function for removing user accounts.
    
    Args:
        username (str): Username of the account to delete
        
    Returns:
        bool: True if user was deleted successfully, False otherwise
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    result = users.delete_one({'username': username})
    client.close()
    if result.deleted_count == 0:
        # Try with different field name
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        result = users.delete_one({'Username': username})
        client.close()
    
    return result.deleted_count > 0


def update_active_borrowing(username, item_id, status):
    """
    Update a user's active borrowing status.
    
    Args:
        username (str): Username of the user
        item_id (str): ID of the borrowed item or None if returning
        status (bool): True if borrowing, False if returning
        
    Returns:
        bool: True if successful, False on error
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        result = users.update_one(
            {'username': username}, 
            {'$set': {
                'active_borrowing': status,
                'borrowed_item': item_id if status else None
            }}
        )
        
        if result.matched_count == 0:
            result = users.update_one(
                {'Username': username}, 
                {'$set': {
                    'active_borrowing': status,
                    'borrowed_item': item_id if status else None
                }}
            )
            
        client.close()
        return result.modified_count > 0
    except Exception as e:
        return False


def get_name(username):
    """
    Retrieve the name that is assosiated with the username.

    Returns:
        str: String of name
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    user = users.find_one({'Username': username})
    name = user.get("name")
    return name


def get_last_name(username):
    """
    Retrieve the last_name that is assosiated with the username.

    Returns:
        str: String of last_name
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    users = db['users']
    user = users.find_one({'Username': username})
    name = user.get("last_name")
    return name


def get_all_users():
    """
    Retrieve all users from the database.
    Administrative function for user management.
    
    Returns:
        list: List of all user documents
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        all_users = list(users.find())
        client.close()
        return all_users
    except Exception as e:
        return []

def update_password(username, new_password):
    """
    Update a user's password with a new one.
    
    Args:
        username (str): Username of the user
        new_password (str): New password to set
        
    Returns:
        bool: True if password was updated successfully, False otherwise
    """
    try:
        if not check_password_strength(new_password):
            return False
            
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        
        # Hash the new password
        hashed_password = hashing(new_password)
        
        # Update the user's password
        result = users.update_one(
            {'Username': username}, 
            {'$set': {'Password': hashed_password}}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
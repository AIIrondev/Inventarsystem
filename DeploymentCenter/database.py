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
Database Interface Module for Inventarsystem Management

This module provides three main classes for interacting with the MongoDB database
specifically for the management application:
- ausleihung: Manages borrowing records with advanced querying
- Inventory: Handles inventory items with management-specific functions
- User: Extended user management with administrative capabilities

These classes are specifically designed for administrative use and contain
methods that should not be accessible to regular users of the system.
"""

from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import ObjectId
import hashlib

class ausleihung:
    """
    Class for managing borrowing records in the database.
    Provides advanced methods for creating, updating, and analyzing borrowing data.
    """
    
    @staticmethod
    def add_ausleihung(item_id, user_id, start):
        """
        Add a new borrowing record to the database.
        
        Args:
            item_id (str): ID of the borrowed item
            user_id (str): ID or username of the borrower
            start (datetime): Start date/time of the borrowing period
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.insert_one({'$set': {'Item': item_id, 'User': user_id, 'Start': start, 'End': 'None'}})
        client.close()
    
    @staticmethod
    def remove_ausleihung(id):
        """
        Remove a borrowing record from the database.
        Administrative function for data cleanup.
        
        Args:
            id (str): ID of the borrowing record to remove
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.delete_one({'_id': ObjectId(id)})
        client.close()
    
    @staticmethod
    def update_ausleihung(id, item_id, user_id, start, end):
        """
        Update an existing borrowing record.
        Allows administrators to correct or modify borrowing data.
        
        Args:
            id (str): ID of the borrowing record to update
            item_id (str): ID of the borrowed item
            user_id (str): ID or username of the borrower
            start (datetime): Start date/time of the borrowing period
            end (datetime): End date/time of the borrowing period
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.update_one({'_id': ObjectId(id)}, {'$set': {'Item': item_id, 'User': user_id, 'Start': start, 'End': end}})
        client.close()
    
    @staticmethod
    def get_ausleihungen():
        """
        Retrieve all borrowing records from the database.
        Used by administrators to view complete borrowing history.
        
        Returns:
            list: List of all borrowing records
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        collection = db['ausleihungen']  
        results = list(collection.find())
        client.close()
        return results

    @staticmethod
    def get_ausleihung(id):
        """
        Retrieve a specific borrowing record by its ID.
        
        Args:
            id (str): ID of the borrowing record to retrieve
            
        Returns:
            dict: The borrowing record data or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'_id': ObjectId(id)})
        client.close()
        return ausleihung.get('$set')

    @staticmethod
    def get_ausleihung_by_user(user_id):
        """
        Retrieve borrowing records for a specific user.
        Used by administrators to track user borrowing history.
        
        Args:
            user_id (str): ID or username of the user
            
        Returns:
            dict: User's borrowing record data or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find({'$set', {'User': user_id}})
        ausleihung = ausleihung["$set"]
        client.close()
        return ausleihung
    
    @staticmethod
    def get_ausleihung_by_item(item_id):
        """
        Retrieve borrowing records for a specific item.
        Used to track item borrowing history.
        
        Args:
            item_id (str): ID of the item
            
        Returns:
            tuple: A tuple containing (ausleihung_id, user_id, start_date, end_date) or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find()
        for ausleihung in ausleihung:
            if ausleihung["$set"]["Item"] == item_id:
                client.close()
                return f"{ausleihung['_id']}", f"{ausleihung['$set']['User']}", f"{ausleihung['$set']['Start']}", f"{ausleihung['$set']['End']}"
        client.close()
        return None


class Inventory:
    """
    Class for managing inventory items in the database.
    Provides methods for creating, updating, and retrieving inventory information
    with administrative capabilities.
    """
    
    @staticmethod
    def add_item(name, ort, beschreibung, image):
        """
        Add a new item to the inventory.
        
        Args:
            name (str): Name of the item
            ort (str): Location of the item
            beschreibung (str): Description of the item
            image (str): Filename of the item's image
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.insert_one({'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': image, 'Verfügbar': True, "Zustandt": 1})
        client.close()

    @staticmethod
    def remove_item(id):
        """
        Remove an item from the inventory.
        Administrator function for removing obsolete or damaged items.
        
        Args:
            id (str): ID of the item to remove
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.delete_one({'_id': ObjectId(id)})
        client.close()
    
    @staticmethod
    def update_item(id, name, ort, beschreibung, image, verfügbar, zustandt):
        """
        Update an existing inventory item.
        Allows administrators to modify all item properties including status.
        
        Args:
            id (str): ID of the item to update
            name (str): Name of the item
            ort (str): Location of the item
            beschreibung (str): Description of the item
            image (str): Filename of the item's image
            verfügbar (bool): Availability status of the item
            zustandt (int): Condition of the item (1=good, 2=fair, 3=poor)
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.update_one({'_id': ObjectId(id)}, {'$set': {'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': image, 'Verfügbar': verfügbar, 'Zustandt': zustandt}})
        client.close()

    @staticmethod
    def update_item_status(id, verfügbar):
        """
        Update the availability status of an inventory item.
        
        Args:
            id (str): ID of the item to update
            verfügbar (bool): New availability status
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.update_one({'_id': ObjectId(id)}, {'$set': {'Verfügbar': verfügbar}})
        client.close()

    @staticmethod
    def get_items():
        """
        Retrieve all inventory items.
        
        Returns:
            list: List of all inventory item documents with string IDs
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items_return = items.find()
        items_list = []
        for item in items_return:
            item['_id'] = str(item['_id'])
            items_list.append(item)
        client.close()
        return items_list
    
    @staticmethod
    def get_item(id):
        """
        Retrieve a specific inventory item by its ID.
        
        Args:
            id (str): ID of the item to retrieve
            
        Returns:
            dict: The inventory item document or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find_one({'_id': ObjectId(id)})
        client.close()
        return item
    
    @staticmethod
    def get_item_by_name(name):
        """
        Retrieve a specific inventory item by its name.
        
        Args:
            name (str): Name of the item to retrieve
            
        Returns:
            dict: The inventory item document or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find_one({'Name': name})
        client.close()
        return item


class User:
    """
    Class for managing user accounts and authentication.
    Provides advanced administrative methods for user management.
    """
    
    def __init__(self):
        """
        Initialize connection to the users collection.
        """
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['Inventarsystem']
        self.users = self.db['users']

    @staticmethod
    def check_password_strength(password):
        """
        Check if a password meets minimum security requirements.
        
        Args:
            password (str): Password to check
            
        Returns:
            bool: True if password is strong enough, False otherwise
        """
        if len(password) < 12:
            return False
        return True

    @staticmethod
    def hashing(password):
        """
        Hash a password using SHA-512.
        
        Args:
            password (str): Password to hash
            
        Returns:
            str: Hexadecimal digest of the hashed password
        """
        return hashlib.sha512(password.encode()).hexdigest()

    @staticmethod
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

    @staticmethod
    def add_user(username, password):
        """
        Add a new user to the database.
        Administrative function for creating user accounts.
        
        Args:
            username (str): Username for the new user
            password (str): Password for the new user
            
        Returns:
            bool: True if user was added successfully, False if password was too weak
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        if not User.check_password_strength(password):
            return False
        users.insert_one({'Username': username, 'Password': User.hashing(password), 'Admin': False, 'active_ausleihung': None})
        client.close()
        return True

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
        return user['Admin']

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def get_all_users():
        """
        Retrieve all users from the database.
        Administrative function for user management.
        
        Returns:
            list: List of all user documents
        """
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']  # Match your actual database name
            users = db['users']
            all_users = list(users.find())
            client.close()
            return all_users
        except Exception as e:
            return []
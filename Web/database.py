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
Database Interface Module for Inventarsystem

This module provides three main classes for interacting with the MongoDB database:
- ausleihung: Manages borrowing records
- Inventory: Handles inventory items management
- User: Manages user accounts and authentication

Each class contains methods for creating, reading, updating, and deleting records
in their respective collections.
"""

from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import ObjectId
import hashlib
import datetime


class ausleihung:
    """
    Class for managing borrowing records in the database.
    Provides methods for creating, updating, and retrieving borrowing information.
    """
    
    @staticmethod
    def add_ausleihung(item_id, user_id, start, end=None):
        """
        Add a new borrowing record to the database.
        
        Args:
            item_id (str): ID of the borrowed item
            user_id (str): ID or username of the borrower
            start (datetime): Start date/time of the borrowing period
            end (datetime, optional): End date/time of the borrowing period, None if item is still borrowed
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.insert_one({
            'Item': item_id, 
            'User': user_id, 
            'Start': start, 
            'End': end if end else None
        })
        client.close()
    
    @staticmethod
    def remove_ausleihung(id):
        """
        Remove a borrowing record from the database.
        
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
        
        Args:
            id (str): ID of the borrowing record to update
            item_id (str): ID of the borrowed item
            user_id (str): ID or username of the borrower
            start (datetime): Start date/time of the borrowing period
            end (datetime): End date/time of the borrowing period
            
        Returns:
            bool: True if successful
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.update_one(
            {'_id': ObjectId(id)}, 
            {'$set': {
                'Item': item_id, 
                'User': user_id, 
                'Start': start, 
                'End': end
            }}
        )
        client.close()
        return True
    
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
            dict: The borrowing record document or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'_id': ObjectId(id)})
        client.close()
        return ausleihung

    @staticmethod
    def get_ausleihung_by_user(user_id):
        """
        Retrieve a borrowing record for a specific user.
        
        Args:
            user_id (str): ID or username of the user
            
        Returns:
            dict: The borrowing record document or None if not found
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'User': user_id})
        client.close()
        return ausleihung
    
    @staticmethod
    def get_ausleihung_by_item(item_id):
        """
        Retrieve an active borrowing record for a specific item.
        
        Args:
            item_id (str): ID of the item
            
        Returns:
            dict: The active borrowing record document or None if not found
        """
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            ausleihungen = db['ausleihungen']

            ausleihung = ausleihungen.find_one({'Item': item_id, 'End': None})

            if not ausleihung:
                ausleihung = ausleihungen.find_one({'item_id': item_id, 'End': None})
            
            client.close()
            return ausleihung
        except Exception as e:
            return None

    @staticmethod
    def add_planned_booking(item_id, user, start_date, end_date, notes=""):
        """
        Add a planned booking for an item

        Args:
            item_id (str): ID of the item to book
            user (str): Username of the person making the booking
            start_date (datetime): When the booking starts
            end_date (datetime): When the booking ends
            notes (str, optional): Additional notes for the booking

        Returns:
            str: ID of the newly created booking
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        planned_bookings = db['planned_bookings']
        
        booking = {
            'Item': item_id,
            'User': user,
            'Start': start_date,
            'End': end_date,
            'Notes': notes,
            'Status': 'planned'  # Status can be: planned, active, completed, cancelled
        }

        result = planned_bookings.insert_one(booking)
        client.close()
        return result.inserted_id

    @staticmethod
    def check_booking_conflict(item_id, start_date, end_date):
        """
        Check if there's a conflict with existing bookings

        Returns:
            bool: True if there's a conflict, False otherwise
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        planned_bookings = db['planned_bookings']
        
        # Check for overlap with existing planned bookings
        overlapping = planned_bookings.find_one({
            'Item': item_id,
            'Status': {'$in': ['planned', 'active']},
            '$or': [
                # New booking starts during existing booking
                {'Start': {'$lte': start_date}, 'End': {'$gte': start_date}},
                # New booking ends during existing booking
                {'Start': {'$lte': end_date}, 'End': {'$gte': end_date}},
                # New booking contains existing booking
                {'Start': {'$gte': start_date}, 'End': {'$lte': end_date}}
            ]
        })
        
        # Also check active borrowings in the ausleihungen collection
        ausleihungen = db['ausleihungen']
        active_borrowing = ausleihungen.find_one({
            'Item': item_id,
            'End': None  # Active borrowings have null End date
        })
        
        client.close()
        return overlapping is not None or active_borrowing is not None

    @staticmethod
    def get_planned_bookings(start=None, end=None):
        """
        Get planned bookings within a date range

        Args:
            start (str, optional): Start date for range
            end (str, optional): End date for range

        Returns:
            list: List of planned bookings
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        planned_bookings = db['planned_bookings']
        
        query = {'Status': {'$in': ['planned', 'active']}}

        if start and end:
            try:
                # Use dateutil parser instead of fromisoformat
                from dateutil import parser
                
                # Parse dates more robustly
                start_date = parser.parse(start)
                end_date = parser.parse(end)
                
                query['$or'] = [
                    # Booking starts in range
                    {'Start': {'$gte': start_date, '$lte': end_date}},
                    # Booking ends in range
                    {'End': {'$gte': start_date, '$lte': end_date}},
                    # Booking spans the entire range
                    {'Start': {'$lte': start_date}, 'End': {'$gte': end_date}}
                ]
            except Exception as e:
                print(f"Warning: Could not parse date range: {start} to {end}. Error: {e}")
                bookings = []
                client.close()
                return bookings

        bookings = list(planned_bookings.find(query))
        client.close()
        return bookings

    @staticmethod
    def get_booking(booking_id):
        """
        Get a specific booking by ID

        Args:
            booking_id (str): ID of the booking

        Returns:
            dict: Booking data or None if not found
        """
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            planned_bookings = db['planned_bookings']
            
            booking = planned_bookings.find_one({'_id': ObjectId(booking_id)})
            client.close()
            return booking
        except:
            return None

    @staticmethod
    def cancel_booking(booking_id):
        """
        Cancel a planned booking

        Args:
            booking_id (str): ID of the booking to cancel

        Returns:
            bool: True if cancelled successfully
        """
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            planned_bookings = db['planned_bookings']
            
            result = planned_bookings.update_one(
                {'_id': ObjectId(booking_id)},
                {'$set': {'Status': 'cancelled'}}
            )
            client.close()
            return result.modified_count > 0
        except:
            return False

    @staticmethod
    def get_bookings_starting_now(current_time):
        """
        Get bookings that should be starting now

        Args:
            current_time (datetime): Current time to check against

        Returns:
            list: List of bookings that should be starting
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        planned_bookings = db['planned_bookings']
        
        # Find bookings where start time is within 5 minutes of current time
        five_min_window = datetime.timedelta(minutes=5)

        bookings = list(planned_bookings.find({
            'Status': 'planned',
            'Start': {'$lte': current_time + five_min_window, 
                      '$gte': current_time - five_min_window}
        }))
        
        client.close()
        return bookings

    @staticmethod
    def get_bookings_ending_now(current_time):
        """
        Get bookings that should be ending now

        Args:
            current_time (datetime): Current time to check against

        Returns:
            list: List of bookings that should be ending
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        planned_bookings = db['planned_bookings']
        
        # Find bookings where end time is within 5 minutes of current time
        five_min_window = datetime.timedelta(minutes=5)

        bookings = list(planned_bookings.find({
            'Status': 'active',
            'End': {'$lte': current_time + five_min_window, 
                    '$gte': current_time - five_min_window}
        }))
        
        client.close()
        return bookings

    @staticmethod
    def mark_booking_active(booking_id):
        """
        Mark a booking as active (item borrowed)

        Args:
            booking_id (str): ID of the booking

        Returns:
            bool: True if updated successfully
        """
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            planned_bookings = db['planned_bookings']
            
            result = planned_bookings.update_one(
                {'_id': ObjectId(booking_id)},
                {'$set': {'Status': 'active'}}
            )
            client.close()
            return result.modified_count > 0
        except:
            return False

    @staticmethod
    def mark_booking_completed(booking_id):
        """
        Mark a booking as completed (item returned)

        Args:
            booking_id (str): ID of the booking

        Returns:
            bool: True if updated successfully
        """
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            planned_bookings = db['planned_bookings']
            
            result = planned_bookings.update_one(
                {'_id': ObjectId(booking_id)},
                {'$set': {'Status': 'completed'}}
            )
            client.close()
            return result.modified_count > 0
        except:
            return False


class Inventory:
    """
    Class for managing inventory items in the database.
    Provides methods for creating, updating, and retrieving inventory information.
    """
    
    @staticmethod
    def add_item(name, ort, beschreibung, images, filter, filter2):
        """
        Add a new item to the inventory.
        
        Args:
            name (str): Name of the item
            ort (str): Location of the item
            beschreibung (str): Description of the item
            images (list): List of image filenames for the item
            filter (list): Primary filter/category for the item
            filter2 (list): Secondary filter/category for the item
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = {
            'Name': name,
            'Ort': ort,
            'Beschreibung': beschreibung,
            'Images': images,
            'Verfuegbar': True,
            'Filter': filter,
            'Filter2': filter2
        }
        items.insert_one(item)
        client.close()

    @staticmethod
    def remove_item(id):
        """
        Remove an item from the inventory.
        
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
    def update_item(id, name, ort, beschreibung, images, verfügbar, filter, filter2):
        """
        Update an existing inventory item.
        
        Args:
            id (str): ID of the item to update
            name (str): Name of the item
            ort (str): Location of the item
            beschreibung (str): Description of the item
            images (list): List of image filenames for the item
            verfügbar (bool): Availability status of the item
            filter (list): Primary filter/category for the item
            filter2 (list): Secondary filter/category for the item
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.insert_one({'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': images, 'Verfuegbar': verfügbar, 'Filter': filter, 'Filter2': filter2})
        client.close()

    @staticmethod
    def update_item_status(id, verfügbar, user=None):
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
        items.update_one({'_id': ObjectId(id)}, {'$set': {'Verfuegbar': verfügbar}})
        items.update_one({'_id': ObjectId(id)}, {'$set': {'User': user}})
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

    @staticmethod
    def get_item_by_filter(filter):
        """
        Retrieve inventory items matching a specific filter/category.
        
        Args:
            filter (str): Filter value to search for
            
        Returns:
            list: Combined list of items matching the filter in primary or secondary category
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find({'Filter': filter})
        item2 = items.find({'Filter2': filter})
        item = item + item2
        client.close()
        return item
    
    @staticmethod
    def get_filter():
        """
        Retrieve all unique filter/category values from the inventory.
        
        Returns:
            list: Combined list of all primary and secondary filter values
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        filters = items.distinct('Filter')
        filters2 = items.distinct('Filter2')
        filters = filters + filters2
        client.close()
        return filters
    
    @staticmethod
    def unstuck_item(id):
        """
        Remove all borrowing records for a specific item to reset its status.
        Used to fix problematic or stuck items.
        
        Args:
            id (str): ID of the item to unstick
            
        Returns:
            None
        """
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.delete_many({'Item': id})
        client.close()


class User:
    """
    Class for managing user accounts and authentication.
    Provides methods for creating, validating, and retrieving user information.
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
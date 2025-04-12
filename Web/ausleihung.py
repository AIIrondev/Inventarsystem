"""
Borrowing Records Management (Ausleihung)
========================================

This module manages borrowing records in the inventory system database.
It provides the core functionality for tracking item borrowings, returns,
and borrowing history.

Key Features:
- Creating new borrowing records when items are checked out
- Updating records when items are returned
- Retrieving borrowing history for reporting
- Searching borrowing records by user, item, or status

Collection Structure:
- ausleihungen: Stores all borrowing records
  - Active borrowings have End=None
  - Completed borrowings have a valid End date/time
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
from bson.objectid import ObjectId
import datetime


# === BORROWING RECORD MANAGEMENT ===

def add_ausleihung(item_id, user_id, start, end=None, notes=""):
    """
    Create a new borrowing record in the database.
    
    Args:
        item_id (str): ID of the borrowed item
        user_id (str): ID or username of the borrower
        start (datetime): Start date/time of the borrowing period
        end (datetime, optional): End date/time of the borrowing period
        notes (str, optional): Additional notes about this borrowing
        
    Returns:
        ObjectId: ID of the new borrowing record
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        ausleihung_data = {
            'Item': item_id,
            'User': user_id,
            'Start': start,
            'End': end,
            'Notes': notes,
            'Created': datetime.datetime.now(),
            'LastUpdated': datetime.datetime.now()
        }
        
        result = ausleihungen.insert_one(ausleihung_data)
        ausleihung_id = result.inserted_id
        
        client.close()
        return ausleihung_id
    except Exception as e:
        # print(f"Error adding ausleihung: {e}") # Log the error
        return None


def update_ausleihung(id, item_id, user_id, start, end, notes=None):
    """
    Update an existing borrowing record.
    
    Args:
        id (str): ID of the borrowing record to update
        item_id (str): ID of the borrowed item
        user_id (str): ID or username of the borrower
        start (datetime): Start date/time of the borrowing period
        end (datetime): End date/time of the borrowing period
        notes (str, optional): Additional notes about this borrowing
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        update_data = {
            'Item': item_id, 
            'User': user_id, 
            'Start': start, 
            'End': end,
            'LastUpdated': datetime.datetime.now()
        }
        
        # Only update notes if provided
        if notes is not None:
            update_data['Notes'] = notes
            
        result = ausleihungen.update_one(
            {'_id': ObjectId(id)}, 
            {'$set': update_data}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        # print(f"Error updating ausleihung: {e}") # Log the error
        return False


def complete_ausleihung(id, end_time=None):
    """
    Mark a borrowing record as complete by setting its end date.
    
    Args:
        id (str): ID of the borrowing record to complete
        end_time (datetime, optional): End time to set (defaults to current time)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if end_time is None:
            end_time = datetime.datetime.now()
            
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        result = ausleihungen.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'End': end_time,
                'LastUpdated': datetime.datetime.now()
            }}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        # print(f"Error completing ausleihung: {e}") # Log the error
        return False


def remove_ausleihung(id):
    """
    Remove a borrowing record from the database.
    Note: Generally, it's better to mark records as complete rather than delete them.
    
    Args:
        id (str): ID of the borrowing record to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        result = ausleihungen.delete_one({'_id': ObjectId(id)})
        client.close()
        return result.deleted_count > 0
    except Exception as e:
        # print(f"Error removing ausleihung: {e}") # Log the error
        return False


# === BORROWING RECORD RETRIEVAL ===

def get_ausleihung(id):
    """
    Retrieve a specific borrowing record by its ID.
    
    Args:
        id (str): ID of the borrowing record to retrieve
        
    Returns:
        dict: The borrowing record document or None if not found
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'_id': ObjectId(id)})
        client.close()
        return ausleihung
    except Exception as e:
        # print(f"Error retrieving ausleihung: {e}") # Log the error
        return None


def get_ausleihungen(include_completed=True):
    """
    Retrieve borrowing records from the database.
    
    Args:
        include_completed (bool): Whether to include completed borrowings
        
    Returns:
        list: List of borrowing records
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        collection = db['ausleihungen']
        
        # If we don't want completed borrowings, filter them out
        query = {} if include_completed else {'End': None}
        results = list(collection.find(query))
        
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving ausleihungen: {e}") # Log the error
        return []


def get_active_ausleihungen():
    """
    Retrieve all active (not returned) borrowing records.
    
    Returns:
        list: List of active borrowing records
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        collection = db['ausleihungen']
        results = list(collection.find({'End': None}))
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving active ausleihungen: {e}") # Log the error
        return []


def get_completed_ausleihungen():
    """
    Retrieve all completed (returned) borrowing records.
    
    Returns:
        list: List of completed borrowing records
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        collection = db['ausleihungen']
        results = list(collection.find({'End': {'$ne': None}}))
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving completed ausleihungen: {e}") # Log the error
        return []


# === SEARCH FUNCTIONS ===

def get_ausleihung_by_user(user_id, active_only=False):
    """
    Retrieve borrowing records for a specific user.
    
    Args:
        user_id (str): ID or username of the user
        active_only (bool): If True, only return active borrowings
        
    Returns:
        list: List of borrowing records for the user
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        query = {'User': user_id}
        if active_only:
            query['End'] = None
            
        results = list(ausleihungen.find(query))
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving ausleihungen for user {user_id}: {e}") # Log the error
        return []


def get_ausleihung_by_item(item_id, include_history=False):
    """
    Retrieve borrowing records for a specific item.
    
    Args:
        item_id (str): ID of the item
        include_history (bool): If True, include all past borrowings
        
    Returns:
        dict or list: The active borrowing record (if include_history=False) 
                    or all borrowing records for this item (if include_history=True)
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        if include_history:
            # Get all borrowings for this item
            results = list(ausleihungen.find({'Item': item_id}))
            client.close()
            return results
        else:
            # Get just the active borrowing
            ausleihung = ausleihungen.find_one({'Item': item_id, 'End': None})
            if not ausleihung:
                ausleihung = ausleihungen.find_one({'item_id': item_id, 'End': None})
            
            client.close()
            return ausleihung
    except Exception as e:
        # print(f"Error retrieving ausleihungen for item {item_id}: {e}") # Log the error
        return [] if include_history else None


def get_ausleihungen_by_date_range(start_date, end_date):
    """
    Retrieve borrowings that were active during a specific date range.
    
    Args:
        start_date (datetime): Start of date range
        end_date (datetime): End of date range
        
    Returns:
        list: List of borrowing records active during the date range
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        # Find borrowings that:
        # 1. Started before end_date AND
        # 2. Either ended after start_date OR haven't ended yet
        query = {
            'Start': {'$lte': end_date},
            '$or': [
                {'End': {'$gte': start_date}},
                {'End': None}
            ]
        }
        
        results = list(ausleihungen.find(query))
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving ausleihungen by date range: {e}") # Log the error
        return []
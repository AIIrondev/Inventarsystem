"""
Module for managing borrowing records in the database.
Provides methods for creating, updating, and retrieving borrowing information.
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
from bson import ObjectId
import datetime


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
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    ausleihungen = db['ausleihungen']
    
    ausleihung_data = {
        'Item': item_id,
        'User': user_id,
        'Start': start,
        'End': end,
        'Notes': notes
    }
    
    result = ausleihungen.insert_one(ausleihung_data)
    ausleihung_id = result.inserted_id
    
    client.close()
    return ausleihung_id

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
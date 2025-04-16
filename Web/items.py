"""
Inventory Items Management
=========================

This module manages inventory items in the database. It provides comprehensive 
functionality for creating, updating, retrieving and filtering inventory items.

Key Features:
- Creating and updating inventory items
- Retrieving items by ID, name, or filters
- Managing item availability status
- Supporting images and categorization
- Retrieving filter/category values for UI components

Collection Structure:
- items: Stores all inventory item records with their metadata
  - Required fields: Name, Ort, Beschreibung
  - Optional fields: Images, Filter, Filter2, Filter3, Anschaffungsjahr, Anschaffungskosten, Code_4
  - Status fields: Verfuegbar, User (if currently borrowed)
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


# === ITEM MANAGEMENT ===

def add_item(name, ort, beschreibung, images=None, filter=None, filter2=None, filter3=None,
             ansch_jahr=None, ansch_kost=None, code_4=None):
    """
    Add a new item to the inventory.
    
    Args:
        name (str): Name of the item
        ort (str): Location of the item
        beschreibung (str): Description of the item
        images (list, optional): List of image filenames for the item
        filter (str, optional): Primary filter/category for the item
        filter2 (str, optional): Secondary filter/category for the item
        filter3 (str, optional): Tertiary filter/category for the item
        ansch_jahr (int, optional): Year of acquisition
        ansch_kost (float, optional): Cost of acquisition
        code_4 (str, optional): 4-digit identification code
        
    Returns:
        ObjectId: ID of the new item or None if failed
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        
        # Set default values for optional parameters
        if images is None:
            images = []
            
        item = {
            'Name': name,
            'Ort': ort,
            'Beschreibung': beschreibung,
            'Images': images,
            'Verfuegbar': True,
            'Filter': filter,
            'Filter2': filter2,
            'Filter3': filter3,
            'Anschaffungsjahr': ansch_jahr,
            'Anschaffungskosten': ansch_kost,
            'Code_4': code_4,
            'Created': datetime.datetime.now(),
            'LastUpdated': datetime.datetime.now()
        }
        result = items.insert_one(item)
        item_id = result.inserted_id
        
        client.close()
        return item_id
    except Exception as e:
        print(f"Error adding item: {e}")
        return None


def remove_item(id):
    """
    Remove an item from the inventory.
    
    Args:
        id (str): ID of the item to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        result = items.delete_one({'_id': ObjectId(id)})
        client.close()
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error removing item: {e}")
        return False


def update_item(id, name, ort, beschreibung, images=None, verfuegbar=True, 
                filter=None, filter2=None, filter3=None, ansch_jahr=None, ansch_kost=None, code_4=None):
    """
    Update an existing inventory item.
    
    Args:
        id (str): ID of the item to update
        name (str): Name of the item
        ort (str): Location of the item
        beschreibung (str): Description of the item
        images (list, optional): List of image filenames for the item
        verfuegbar (bool, optional): Availability status of the item
        filter (str, optional): Primary filter/category for the item
        filter2 (str, optional): Secondary filter/category for the item
        filter3 (str, optional): Tertiary filter/category for the item
        ansch_jahr (int, optional): Year of acquisition
        ansch_kost (float, optional): Cost of acquisition
        code_4 (str, optional): 4-digit identification code
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        
        # Set default values for optional parameters
        if images is None:
            images = []
            
        update_data = {
            'Name': name,
            'Ort': ort,
            'Beschreibung': beschreibung,
            'Images': images,
            'Verfuegbar': verfuegbar,
            'Filter': filter,
            'Filter2': filter2,
            'Filter3': filter3,
            'Anschaffungsjahr': ansch_jahr,
            'Anschaffungskosten': ansch_kost,
            'Code_4': code_4,
            'LastUpdated': datetime.datetime.now()
        }
        
        result = items.update_one(
            {'_id': ObjectId(id)},
            {'$set': update_data}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating item: {e}")
        return False


def update_item_status(id, verfuegbar, user=None):
    """
    Update the availability status of an inventory item.
    
    Args:
        id (str): ID of the item to update
        verfuegbar (bool): New availability status
        user (str, optional): Username of person who borrowed the item
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        
        update_data = {
            'Verfuegbar': verfuegbar,
            'LastUpdated': datetime.datetime.now()
        }
        
        if user is not None:
            update_data['User'] = user
        elif verfuegbar:
            # If item is being marked as available, clear the user field
            update_data['$unset'] = {'User': ""}
            
        result = items.update_one(
            {'_id': ObjectId(id)},
            {'$set': update_data}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating item status: {e}")
        return False


# === ITEM RETRIEVAL ===

def get_items():
    """
    Retrieve all inventory items.
    
    Returns:
        list: List of all inventory item documents with string IDs
    """
    try:
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
    except Exception as e:
        print(f"Error retrieving items: {e}")
        return []


def get_available_items():
    """
    Retrieve all available inventory items.
    
    Returns:
        list: List of available inventory item documents with string IDs
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items_return = items.find({'Verfuegbar': True})
        items_list = []
        for item in items_return:
            item['_id'] = str(item['_id'])
            items_list.append(item)
        client.close()
        return items_list
    except Exception as e:
        print(f"Error retrieving available items: {e}")
        return []


def get_borrowed_items():
    """
    Retrieve all currently borrowed inventory items.
    
    Returns:
        list: List of borrowed inventory item documents with string IDs
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items_return = items.find({'Verfuegbar': False})
        items_list = []
        for item in items_return:
            item['_id'] = str(item['_id'])
            items_list.append(item)
        client.close()
        return items_list
    except Exception as e:
        print(f"Error retrieving borrowed items: {e}")
        return []


def get_item(id):
    """
    Retrieve a specific inventory item by its ID.
    
    Args:
        id (str): ID of the item to retrieve
        
    Returns:
        dict: The inventory item document or None if not found
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find_one({'_id': ObjectId(id)})
        client.close()
        return item
    except Exception as e:
        print(f"Error retrieving item: {e}")
        return None


def get_item_by_name(name):
    """
    Retrieve a specific inventory item by its name.
    
    Args:
        name (str): Name of the item to retrieve
        
    Returns:
        dict: The inventory item document or None if not found
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find_one({'Name': name})
        client.close()
        return item
    except Exception as e:
        print(f"Error retrieving item by name: {e}")
        return None


def get_items_by_filter(filter_value):
    """
    Retrieve inventory items matching a specific filter/category.
    
    Args:
        filter_value (str): Filter value to search for
        
    Returns:
        list: List of items matching the filter in primary, secondary, or tertiary category
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        
        # Use $or to find matches in any filter field
        query = {
            '$or': [
                {'Filter': filter_value},
                {'Filter2': filter_value},
                {'Filter3': filter_value}
            ]
        }
        
        results = list(items.find(query))
        client.close()
        
        # Convert ObjectId to string
        for item in results:
            item['_id'] = str(item['_id'])
            
        return results
    except Exception as e:
        print(f"Error retrieving items by filter: {e}")
        return []


def get_filters():
    """
    Retrieve all unique filter/category values from the inventory.
    
    Returns:
        list: Combined list of all primary, secondary and tertiary filter values
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        filters = items.distinct('Filter')
        filters2 = items.distinct('Filter2')
        filters3 = items.distinct('Filter3')
        
        # Combine filters and remove None/empty values
        all_filters = [f for f in filters + filters2 + filters3 if f]
        
        # Remove duplicates while preserving order
        unique_filters = []
        for f in all_filters:
            if f not in unique_filters:
                unique_filters.append(f)
                
        client.close()
        return unique_filters
    except Exception as e:
        print(f"Error retrieving filters: {e}")
        return []


def get_primary_filters():
    """
    Retrieve all unique primary filter values.
    
    Returns:
        list: List of all primary filter values
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        filters = [f for f in items.distinct('Filter') if f]
        client.close()
        return filters
    except Exception as e:
        print(f"Error retrieving primary filters: {e}")
        return []


def get_secondary_filters():
    """
    Retrieve all unique secondary filter values.
    
    Returns:
        list: List of all secondary filter values
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        filters = [f for f in items.distinct('Filter2') if f]
        client.close()
        return filters
    except Exception as e:
        print(f"Error retrieving secondary filters: {e}")
        return []


def get_tertiary_filters():
    """
    Retrieve all unique tertiary filter values.
    
    Returns:
        list: List of all tertiary filter values
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        filters = [f for f in items.distinct('Filter3') if f]
        client.close()
        return filters
    except Exception as e:
        print(f"Error retrieving tertiary filters: {e}")
        return []


def get_item_by_code_4(code_4):
    """
    Retrieve inventory items matching a specific 4-digit code.
    
    Args:
        code_4 (str): 4-digit code to search for
        
    Returns:
        list: List of items matching the code
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        results = list(items.find({"Code_4": code_4}))
        
        # Convert ObjectId to string
        for item in results:
            item['_id'] = str(item['_id'])
            
        client.close()
        return results
    except Exception as e:
        print(f"Error retrieving item by code: {e}")
        return []


# === MAINTENANCE FUNCTIONS ===

def unstuck_item(id):
    """
    Remove all borrowing records for a specific item to reset its status.
    Used to fix problematic or stuck items.
    
    Args:
        id (str): ID of the item to unstick
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        result = ausleihungen.delete_many({'Item': id})
        
        # Also reset the item status
        items = db['items']
        items.update_one(
            {'_id': ObjectId(id)},
            {
                '$set': {
                    'Verfuegbar': True,
                    'LastUpdated': datetime.datetime.now()
                },
                '$unset': {'User': ""}
            }
        )
        
        client.close()
        return True
    except Exception as e:
        print(f"Error unsticking item: {e}")
        return False
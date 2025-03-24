"""
Module for managing inventory items in the database.
Provides methods for creating, updating, and retrieving inventory information.
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


def add_item(name, ort, beschreibung, images, filter, filter2, ansch_jahr, ansch_kost, code_4):
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
        'Filter2': filter2,
        'Anschaffungsjahr': ansch_jahr,
        'Anschaffungskosten': ansch_kost,
        'Code_4': code_4
    }
    items.insert_one(item)
    client.close()


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


def update_item(id, name, ort, beschreibung, images, verfügbar, filter, filter2, ansch_jahr, ansch_kost, code_4):
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
    items.insert_one({'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': images, 'Verfuegbar': verfügbar, 'Filter': filter, 'Filter2': filter2, 'Anschaffungsjahr': ansch_jahr, 'Anschaffungskosten': ansch_kost, 'Code_4': code_4})
    client.close()


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


def get_item_code_4(code_4):
    """
    
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    items = db['items']
    item = items.find({"Code_4": code_4})

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
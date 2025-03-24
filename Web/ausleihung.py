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
    Add a new borrowing record to the database.
    
    Args:
        item_id (str): ID of the borrowed item
        user_id (str): ID or username of the borrower
        start (datetime): Start date/time of the borrowing period
        end (datetime, optional): End date/time of the borrowing period, None if item is still borrowed
        notes (str, optional): Additional notes for the borrowing
        
    Returns:
        str: ID of the new ausleihung record, or None if failed
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        record = {
            'Item': item_id, 
            'User': user_id, 
            'Start': start, 
            'End': end,
            'Notes': notes,
            'Created': datetime.datetime.now()
        }
        
        result = ausleihungen.insert_one(record)
        client.close()
        
        if result.inserted_id:
            return str(result.inserted_id)
        return None
    except Exception as e:
        print(f"Error adding ausleihung: {e}")
        return None

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
    
def get_bookings_starting_now(current_time):
    """
    Get bookings that should start now or in the recent past
    Args:
        current_time: Current datetime
    Returns:
        List of bookings that should start now
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    booking_collection = db['planned_bookings']
    # Create a time window - look at bookings starting in the past hour
    # This ensures we catch any bookings that might have been missed
    start_time = current_time - datetime.timedelta(hours=1)
    end_time = current_time + datetime.timedelta(minutes=1)
    # Find bookings that:
    # 1. Have status 'planned'
    # 2. Start time is in the past or right now
    # 3. Don't have an AusleihungId yet
    query = {
        'Status': 'planned',
        'Start': {'$lte': end_time, '$gte': start_time},
        'AusleihungId': {'$exists': False}
    }
    try:
        bookings = list(booking_collection.find(query))
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting bookings starting now: {e}")
        client.close()
        return []
    
def get_bookings_ending_now(current_time):
    """
    Get bookings that should end now (rounded to minutes)
    Args:
        current_time: Current datetime
    Returns:
        List of bookings that should end now
    """
    client = MongoClient('localhost', 27017)
    db = client['Inventarsystem']
    booking_collection = db['planned_bookings']
    # Round current time to the nearest minute
    current_hour = current_time.hour
    current_minute = current_time.minute
    end_time = current_time.replace(hour=current_hour, minute=current_minute, 
                                    second=0, microsecond=0)
    # Create a window - look at bookings ending in this hour
    next_minute = end_time + datetime.timedelta(minutes=1)
    # Find bookings that:
    # 1. Have status 'active'
    # 2. Have end date in this minute window
    query = {
        'Status': 'active',
        'End': {'$gte': end_time, '$lt': next_minute}
    }
    try:
        bookings = booking_collection.find(query)
        return list(bookings)
    except Exception as e:
        print(f"Error getting bookings ending now: {e}")
        return []
    

def mark_booking_active(booking_id, ausleihung_id=None):
    """
    Mark a planned booking as active and link it to an ausleihung record
    
    Args:
        booking_id (str): ID of the booking to mark as active
        ausleihung_id (str, optional): ID of the associated ausleihung record
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        booking_collection = db['planned_bookings']
        
        update_data = {
            'Status': 'active',
            'LastUpdated': datetime.datetime.now()
        }
        
        if ausleihung_id:
            update_data['AusleihungId'] = ausleihung_id
            
        result = booking_collection.update_one(
            {'_id': ObjectId(booking_id)},
            {'$set': update_data}
        )
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error marking booking active: {e}")
        return False
    

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
        booking_collection = db['planned_bookings']
        
        result = booking_collection.update_one(
            {'_id': ObjectId(booking_id)},
            {'$set': {
                'Status': 'completed',
                'LastUpdated': datetime.datetime.now()
            }}
        )
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error marking booking completed: {e}")
        return False
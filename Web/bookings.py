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
import ausleihung as au


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
    Get all bookings that should start now (within a window of time)
    
    Args:
        current_time (datetime): Current time to check against
    
    Returns:
        list: List of bookings that should start now
    """
    try:
        # Define a window of time (1 hour before and after now)
        h_1 = datetime.timedelta(hours=1)
        start_time = current_time - h_1
        end_time = current_time + h_1
        
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        # Use planned_bookings collection instead of bookings
        bookings_collection = db['planned_bookings']
        
        # Print diagnostic info
        print(f"start: {start_time}, end: {end_time}")
        query = {
            'Status': 'planned',
            'Start': {
                '$lte': end_time,
                '$gte': start_time
            },
            'AusleihungId': {'$exists': False}  # Not yet processed
        }
        print(f"query: {query}")
        
        # Find bookings that should start now
        bookings = list(bookings_collection.find(query))
        print(f"Bookings: {bookings}")
        
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting bookings starting now: {e}")
        return []

def get_bookings_ending_now(current_time):
    """
    Get all bookings that should end now (within a window of time)
    
    Args:
        current_time (datetime): Current time to check against
    
    Returns:
        list: List of bookings that should end now
    """
    try:
        # Define a window of time (e.g., 5 minutes before and after now)
        window = datetime.timedelta(minutes=5)
        start_time = current_time - window
        end_time = current_time + window
        
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        bookings_collection = db['bookings']
        
        # Find bookings that should end now
        bookings = list(bookings_collection.find({
            'Status': 'active',
            'End': {
                '$lte': end_time,
                '$gte': start_time
            }
        }))
        
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting bookings ending now: {e}")
        return []

def mark_booking_active(booking_id):
    """
    Mark a booking as active and create an ausleihung record
    
    Args:
        booking_id (str): ID of the booking to mark as active
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        bookings_collection = db['planned_bookings']
        
        # Find the booking
        booking = bookings_collection.find_one({'_id': ObjectId(booking_id)})
        if not booking:
            print(f"Booking {booking_id} not found")
            client.close()
            return False
        
        # Import ausleihung module here to avoid circular imports
        import ausleihung as au
        
        # Create ausleihung record
        print(f"Creating ausleihung for booking {booking_id}, item {booking['Item']}, user {booking['User']}")
        ausleihung_id = au.add_ausleihung(
            booking['Item'],
            booking['User'],
            booking['Start'],
            booking['End'],
            booking.get('Notes', '')
        )
        
        if not ausleihung_id:
            print(f"Failed to create ausleihung record for booking {booking_id}")
            client.close()
            return False
        
        # Important: Update booking status to "active" (not removing it)
        bookings_collection.update_one(
            {'_id': ObjectId(booking_id)},
            {'$set': {
                'Status': 'active',
                'AusleihungId': str(ausleihung_id)
            }}
        )
        
        print(f"Successfully activated booking {booking_id} with ausleihung {ausleihung_id}")
        client.close()
        return True
    except Exception as e:
        print(f"Error marking booking as active: {e}")
        return False

def get_planned_bookings(start=None, end=None):
    """
    Get all planned bookings within a date range
    
    Args:
        start (str): Start date in ISO format
        end (str): End date in ISO format
        
    Returns:
        list: List of planned bookings
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        bookings_collection = db['bookings']
        
        # Convert string dates to datetime if provided
        query = {'Status': 'planned'}
        if start and end:
            try:
                # Try to parse the dates
                start_date = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_date = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
                
                # Add date filter
                query['$or'] = [
                    # Booking starts within the range
                    {'Start': {'$gte': start_date, '$lte': end_date}},
                    # Booking ends within the range
                    {'End': {'$gte': start_date, '$lte': end_date}},
                    # Booking spans the entire range
                    {'$and': [{'Start': {'$lte': start_date}}, {'End': {'$gte': end_date}}]}
                ]
            except ValueError:
                # If date parsing fails, ignore the date filter
                pass
        
        # Get planned bookings
        bookings = list(bookings_collection.find(query))
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting planned bookings: {e}")
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

def get_active_bookings(start=None, end=None):
    """
    Get active bookings (bookings that have been activated but still in the planned_bookings collection)
    
    Args:
        start (str): Start date in ISO format
        end (str): End date in ISO format
        
    Returns:
        list: List of active bookings
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        bookings_collection = db['planned_bookings']
        
        query = {'Status': 'active'}
        
        # Add date filter if provided
        if start and end:
            try:
                # Try to parse the dates
                start_date = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_date = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
                
                # Add date filter
                query['$or'] = [
                    # Booking starts within the range
                    {'Start': {'$gte': start_date, '$lte': end_date}},
                    # Booking ends within the range
                    {'End': {'$gte': start_date, '$lte': end_date}},
                    # Booking spans the entire range
                    {'$and': [{'Start': {'$lte': start_date}}, {'End': {'$gte': end_date}}]}
                ]
            except ValueError:
                # If date parsing fails, ignore the date filter
                pass
        
        # Get active bookings
        print(f"Query for active bookings: {query}")
        bookings = list(bookings_collection.find(query))
        print(f"Found {len(bookings)} active bookings")
        
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting active bookings: {e}")
        return []
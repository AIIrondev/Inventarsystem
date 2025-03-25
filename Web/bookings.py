"""
Booking Management System
========================

This module handles all booking-related operations for the inventory system.
It manages the lifecycle of bookings from creation through activation to completion.

Key Features:
- Creating planned bookings for items
- Checking for booking conflicts
- Retrieving bookings by status (planned, active, completed)
- Managing booking state transitions
- Integration with the ausleihung (borrowing) system

Collection Structure:
- planned_bookings: Stores all booking records with their current status
  - Status values: 'planned', 'active', 'completed', 'cancelled'

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
import ausleihung as au


# === BOOKING CREATION AND MANAGEMENT ===

def add_planned_booking(item_id, user, start_date, end_date, notes=""):
    """
    Create a new planned booking for an item.
    
    Args:
        item_id (str): ID of the item to book
        user (str): Username of the person making the booking
        start_date (datetime): When the booking starts
        end_date (datetime): When the booking ends
        notes (str, optional): Additional notes for the booking

    Returns:
        ObjectId: ID of the newly created booking
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
        'Status': 'planned',  # Status can be: planned, active, completed, cancelled
        'LastUpdated': datetime.datetime.now()
    }
    result = planned_bookings.insert_one(booking)
    client.close()
    return result.inserted_id


def check_booking_conflict(item_id, start_date, end_date):
    """
    Check if there's a conflict with existing bookings or active borrowings.
    
    Args:
        item_id (str): ID of the item to check
        start_date (datetime): Proposed booking start date
        end_date (datetime): Proposed booking end date

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


def cancel_booking(booking_id):
    """
    Cancel a planned booking.
    
    Args:
        booking_id (str): ID of the booking to cancel
        
    Returns:
        bool: True if cancelled successfully, False otherwise
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        planned_bookings = db['planned_bookings']
        
        result = planned_bookings.update_one(
            {'_id': ObjectId(booking_id)},
            {'$set': {
                'Status': 'cancelled',
                'LastUpdated': datetime.datetime.now()
            }}
        )
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error cancelling booking: {e}")
        return False


# === BOOKING STATE TRANSITIONS ===

def mark_booking_active(booking_id, ausleihung_id=None):
    """
    Mark a planned booking as active and link it to an ausleihung record.
    
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
        
        # First, verify the booking exists and is in 'planned' status
        booking = booking_collection.find_one({'_id': ObjectId(booking_id)})
        if not booking or booking.get('Status') != 'planned':
            print(f"Booking {booking_id} not found or not in planned status")
            client.close()
            return False
        
        # If no ausleihung_id provided, create the ausleihung record
        if not ausleihung_id:
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
        
        # Update the booking status
        update_data = {
            'Status': 'active',
            'AusleihungId': str(ausleihung_id),
            'LastUpdated': datetime.datetime.now()
        }
            
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
    Mark a booking as completed (item returned).
    
    Args:
        booking_id (str): ID of the booking to mark as completed
        
    Returns:
        bool: True if updated successfully, False otherwise
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


# === BOOKING RETRIEVAL ===

def get_booking(booking_id):
    """
    Get a specific booking by ID.
    
    Args:
        booking_id (str): ID of the booking to retrieve
        
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
    except Exception as e:
        print(f"Error retrieving booking: {e}")
        return None


def get_planned_bookings(start=None, end=None):
    """
    Get all planned bookings within a date range.
    
    Args:
        start (str): Start date in ISO format
        end (str): End date in ISO format
        
    Returns:
        list: List of planned bookings
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        bookings_collection = db['planned_bookings']
        
        query = {'Status': 'planned'}
        
        # Add date range filter if provided
        if start and end:
            try:
                from dateutil import parser
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
        
        bookings = list(bookings_collection.find(query))
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting planned bookings: {e}")
        return []


def get_active_bookings(start=None, end=None):
    """
    Get active bookings within a date range.
    
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
        
        # Add date range filter if provided
        if start and end:
            try:
                from dateutil import parser
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
        
        bookings = list(bookings_collection.find(query))
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting active bookings: {e}")
        return []


def get_completed_bookings(start=None, end=None):
    """
    Get completed bookings within a date range.
    
    Args:
        start (str): Start date in ISO format
        end (str): End date in ISO format
        
    Returns:
        list: List of completed bookings
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        bookings_collection = db['planned_bookings']
        
        query = {'Status': 'completed'}
        
        # Add date range filter if provided
        if start and end:
            try:
                from dateutil import parser
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
        
        bookings = list(bookings_collection.find(query))
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting completed bookings: {e}")
        return []


# === AUTOMATED BOOKING PROCESSING ===

def get_bookings_starting_now(current_time):
    """
    Get all bookings that should start now (within a time window).
    
    This function is used by the scheduler to find bookings that should be 
    automatically activated based on their start time.
    
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
        bookings_collection = db['planned_bookings']
        
        query = {
            'Status': 'planned',
            'Start': {
                '$lte': end_time,
                '$gte': start_time
            },
            'AusleihungId': {'$exists': False}  # Not yet processed
        }
        
        print(f"Looking for bookings starting between {start_time} and {end_time}")
        bookings = list(bookings_collection.find(query))
        print(f"Found {len(bookings)} bookings to activate")
        
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting bookings starting now: {e}")
        return []


def get_bookings_ending_now(current_time):
    """
    Get bookings that should end now (within a time window).
    
    This function is used by the scheduler to find active bookings that should be
    automatically completed based on their end time.
    
    Args:
        current_time (datetime): Current time to check against
    
    Returns:
        list: List of bookings that should end now
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        booking_collection = db['planned_bookings']
        
        # Create a window of time (5 minutes before and after)
        window = datetime.timedelta(minutes=5)
        start_time = current_time - window
        end_time = current_time + window
        
        # Find bookings that:
        # 1. Have status 'active'
        # 2. Have end date within this time window
        query = {
            'Status': 'active',
            'End': {'$gte': start_time, '$lte': end_time}
        }
        
        print(f"Looking for bookings ending between {start_time} and {end_time}")
        bookings = list(booking_collection.find(query))
        print(f"Found {len(bookings)} bookings to complete")
        
        client.close()
        return bookings
    except Exception as e:
        print(f"Error getting bookings ending now: {e}")
        return []
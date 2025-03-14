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
import hashlib
from tkinter import messagebox


class ausleihung:
    def add_ausleihung(item_id, user_id, start, end=None):
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
    
    def remove_ausleihung(id):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.delete_one({'_id': ObjectId(id)})
        client.close()
    
    def update_ausleihung(id, item_id, user_id, start, end):
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
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen_return = ausleihungen.find()
        client.close()
        return ausleihungen_return

    def get_ausleihung(id):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'_id': ObjectId(id)})
        client.close()
        return ausleihung  # Rückgabe des gesamten Dokuments ohne .get('$set')

    def get_ausleihung_by_user(user_id):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'User': user_id})  # Korrekter MongoDB-Abfrageausdruck
        client.close()
        return ausleihung
    
    def get_ausleihung_by_item(item_id):
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            ausleihungen = db['ausleihungen']
            
            # Debug output
            print(f"Looking for ausleihung with item_id: {item_id}")
            
            # Try different field names that might contain the item ID
            ausleihung = ausleihungen.find_one({'Item': item_id})
            if not ausleihung:
                ausleihung = ausleihungen.find_one({'item_id': item_id})
            
            print(f"Found ausleihung: {ausleihung}")
            
            client.close()
            
            if ausleihung:
                # Return a dictionary for more flexible handling
                return ausleihung
            else:
                return None
        except Exception as e:
            print(f"Error in get_ausleihung_by_item: {e}")
            return None

class Inventory:
    def add_item(name, ort, beschreibung, images, filter, filter2):
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

    def remove_item(id):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.delete_one({'_id': ObjectId(id)})
        client.close()
    
    def update_item(id, name, ort, beschreibung, images, verfügbar, filter, filter2):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.insert_one({'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': images, 'Verfuegbar': verfügbar, 'Filter': filter, 'Filter2': filter2})
        client.close()

    def update_item_status(id, verfügbar):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        items.update_one({'_id': ObjectId(id)}, {'$set': {'Verfuegbar': verfügbar}})
        client.close()

    @staticmethod
    def get_items():
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
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find_one({'_id': ObjectId(id)})
        client.close()
        return item
    
    def get_item_by_name(name):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find_one({'Name': name})
        client.close()
        return item

    def get_item_by_filter(filter):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        item = items.find({'Filter': filter})
        item2 = items.find({'Filter2': filter})
        item = item + item2
        client.close()
        return item
    
    def get_filter():
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        items = db['items']
        filters = items.distinct('Filter')
        filters2 = items.distinct('Filter2')
        filters = filters + filters2
        client.close()
        return filters
    
    def unstuck_item(id):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihungen.delete_many({'Item': id})
        client.close()


class User:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['Inventarsystem']
        self.users = self.db['users']

    @staticmethod
    def check_password_strength(password):
        if len(password) < 12:
            messagebox.showerror('Critical', 'Password is too weak (12 characters required)\n youre request has been denied')
            return False
        return True

    @staticmethod
    def hashing(password):
        return hashlib.sha512(password.encode()).hexdigest()

    @staticmethod
    def check_nm_pwd(username, password):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        hashed_password = hashlib.sha512(password.encode()).hexdigest()
        user = users.find_one({'Username': username, 'Password': hashed_password})
        client.close()
        return user

    @staticmethod
    def add_user(username, password):
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
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        users_return = users.find_one({'Username': username})
        client.close()
        return users_return

    @staticmethod
    def check_admin(username):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        user = users.find_one({'Username': username})
        client.close()
        return user['Admin']

    @staticmethod
    def update_active_ausleihung(username, id_item, ausleihung):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        users.update_one({'Username': username}, {'$set': {'active_ausleihung': {'Item': id_item, 'Ausleihung': ausleihung}}})
        client.close()
        return True

    @staticmethod
    def get_active_ausleihung(username):
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        user = users.find_one({'Username': username})
        return user['active_ausleihung']

    @staticmethod
    def has_active_borrowing(username):
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']  # Case-sensitive database name
            users = db['users']
            
            # Debug output
            print(f"Checking active borrowing status for user: {username}")
            
            # Try both lowercase and capitalized field names
            user = users.find_one({'username': username})
            if not user:
                user = users.find_one({'Username': username})
                
            if not user:
                print(f"User {username} not found in database")
                client.close()
                return False
                
            has_active = user.get('active_borrowing', False)
            print(f"User {username} active_borrowing status: {has_active}")
            
            client.close()
            return has_active
        except Exception as e:
            print(f"Error in has_active_borrowing: {e}")
            return False

    @staticmethod
    def update_active_borrowing(username, item_id, status):
        try:
            client = MongoClient('localhost', 27017)
            db = client['Inventarsystem']
            users = db['users']
            
            # Debug output
            print(f"Updating borrowing status for {username}: {status} with item {item_id}")
            
            # Try both field names to ensure we update the right document
            result = users.update_one(
                {'username': username}, 
                {'$set': {
                    'active_borrowing': status,
                    'borrowed_item': item_id if status else None
                }}
            )
            
            if result.matched_count == 0:
                # Try with capitalized field name
                result = users.update_one(
                    {'Username': username}, 
                    {'$set': {
                        'active_borrowing': status,
                        'borrowed_item': item_id if status else None
                    }}
                )
                
            print(f"Update result: {result.modified_count} documents modified")
            client.close()
            return result.modified_count > 0
        except Exception as e:
            print(f"Error in update_active_borrowing: {e}")
            return False

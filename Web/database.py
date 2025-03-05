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
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import hashlib
from tkinter import messagebox


class Auslehungen:
    def add_auslehnung(item_id, user_id, start, end):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnungen.insert_one({'Item': item_id, 'User': user_id, 'Start': start, 'End': end})
        client.close()
    
    def remove_auslehnung(id):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnungen.delete_one({'_id': ObjectId(id)})
        client.close()
    
    def update_auslehnung(id, item_id, user_id, start, end):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnungen.update_one({'_id': ObjectId(id)}, {'$set': {'Item': item_id, 'User': user_id, 'Start': start, 'End': end}})
        client.close()
    
    def get_auslehnungen():
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnungen_return = auslehnungen.find()
        client.close()
        return auslehnungen_return

    def get_auslehnung(id):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnung = auslehnungen.find_one({'_id': ObjectId(id)})
        client.close()
        return auslehnung

    def get_auslehnung_by_user(user_id):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnung = auslehnungen.find_one({'User': user_id})
        client.close()
        return auslehnung
    
    def get_auslehnung_by_item(item_id):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        auslehnungen = db['auslehnungen']
        auslehnung = auslehnungen.find_one({'Item': item_id})
        client.close()
        return auslehnung


class Inventory:
    def add_item(name, ort, beschreibung, image):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        items = db['items']
        items.insert_one({'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': image, 'Verfügbar': True, "Zustandt": 1})
        client.close()

    def remove_item(id):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        items = db['items']
        items.delete_one({'_id': ObjectId(id)})
        client.close()
    
    def update_item(id, name, ort, beschreibung, image, verfügbar, zustandt):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        items = db['items']
        items.update_one({'_id': ObjectId(id)}, {'$set': {'Name': name, 'Ort': ort, 'Beschreibung': beschreibung, 'Image': image, 'Verfügbar': verfügbar, 'Zustandt': zustandt}})
        client.close()

    def get_items():
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        items = db['items']
        items_return = items.find()
        items_return = list(items_return)
        client.close()
        return items_return

    def get_item(id):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        items = db['items']
        item = items.find_one({'_id': ObjectId(id)})
        client.close()
        return item
    
    def get_item_by_name(name):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        items = db['items']
        item = items.find_one({'Name': name})
        client.close()
        return item


class User:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['Chatsystem']
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
        db = client['Chatsystem']
        users = db['users']
        hashed_password = hashlib.sha512(password.encode()).hexdigest()
        user = users.find_one({'Username': username, 'Password': hashed_password})
        client.close()
        return user

    @staticmethod
    def add_user(username, password):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        users = db['users']
        if not User.check_password_strength(password):
            return False
        users.insert_one({'Username': username, 'Password': User.hashing(password)})
        client.close()
        return True

    @staticmethod
    def get_user(username):
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        users = db['users']
        users_return = users.find_one({'Username': username})
        client.close()
        return users_return

    @staticmethod
    def get_admins():
        client = MongoClient('localhost', 27017)
        db = client['Chatsystem']
        users = db['users']
        users_return = users.find({'Admin': True})
        client.close()
        return users_return
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import hashlib
from tkinter import messagebox

class Database: # chat database class, preset: (_id, name, message, chat_room)
    def __init__(self, registry):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['Inventar']
        self.register = self.db[registry]
        if Register_Database().get_register({'name': registry}) == None:
            Register_Database().add_register({'name': registry})

    def add_item(self, item):
        self.register.insert_one(item)
    
    def get_item(self, item):
        return self.register.find_one(item)

    def get_all_items(self):
        return self.register.find()
    
    def update_item(self, item, new_item):
        self.register.update_one(item, new_item)
    
    def delete_item(self, item):
        self.register.delete_one(item)

    def delete_all_items(self):
        self.register.delete_many({})
    
    def delete_register(self):
        self.db.drop_collection(self.register)

    def close(self):
        self.client.close()

class Register_Database:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['Inventar']
        self.register = self.db['registry']
    
    def add_register(self, register):
        self.register.insert_one(register)
    
    def get_all_registers(self):
        return self.register.find()
    
    def delete_register(self, register):
        self.register.delete_one(register)
    
    def delete_all_registers(self):
        self.register.delete_many({})
    
    def get_register(self, register):
        return self.register.find_one(register)

    def close(self):
        self.client.close()
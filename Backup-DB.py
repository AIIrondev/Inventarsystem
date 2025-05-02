import os
import csv
from pymongo import MongoClient
from bson.json_util import dumps
from datetime import datetime

# Configuration
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "Inventarsystem"
BACKUP_DIR = f"mongodb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def export_collection_to_csv(db, collection_name, backup_path):
    collection = db[collection_name]
    documents = list(collection.find())

    if not documents:
        print(f"No data in collection: {collection_name}")
        return

    keys = set()
    for doc in documents:
        keys.update(doc.keys())

    with open(os.path.join(backup_path, f"{collection_name}.csv"), mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=sorted(keys))
        writer.writeheader()
        for doc in documents:
            # Convert ObjectId to string
            doc = {k: str(v) for k, v in doc.items()}
            writer.writerow(doc)

def backup_mongodb_to_csv():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection_names = db.list_collection_names()

    for collection_name in collection_names:
        print(f"Exporting {collection_name}...")
        export_collection_to_csv(db, collection_name, BACKUP_DIR)

    print(f"Backup completed to directory: {BACKUP_DIR}")

if __name__ == "__main__":
    backup_mongodb_to_csv()
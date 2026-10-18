import os 

from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "sistema_medico")

_client = None
db = None

def get_db():
    global _client, db
    if _client is None:
        _client = MongoClient(MONGO_URI)
        db = _client[MONGO_DB]
    return db

def close_db():
    global _client
    if _client:
        _client.close()
        _client = None

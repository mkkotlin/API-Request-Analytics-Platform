from pymongo import MongoClient
from django.conf import settings


client = MongoClient(
    settings.MONGO_URI,
    serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    connectTimeoutMS=settings.MONGO_CONNECT_TIMEOUT_MS,
    socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
)

db = client[settings.MONGO_DB_NAME]
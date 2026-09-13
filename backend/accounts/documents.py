from datetime import datetime, timezone

from uuid import uuid4
from pymongo import ASCENDING



class UserDocument:
    collection_name = "users"

    @staticmethod
    def create_index(db):
        collection = db[UserDocument.collection_name]

        collection.create_index(
            [("id", ASCENDING)], 
            unique=True
        )
        collection.create_index(
            [("email", ASCENDING)],
            unique=True
        )
        collection.create_index(
            [("username", ASCENDING)],
            unique=True
        )
    
    @staticmethod
    def create(username, email, password_hash, role="USER"):
        return {
            "id": str(uuid4()),
            "username": username,
            "email": email,
            "password": password_hash,
            "role": role,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }

class RefreshTokenDocument:

    collection_name = "refresh_tokens"

    @staticmethod
    def create(user_id, jti, expires_at):
        return {
        "jti": jti,
        "user_id": user_id,
        "expires_at": expires_at,
        "revoked": False,
        "created_at": datetime.now(timezone.utc),
        }
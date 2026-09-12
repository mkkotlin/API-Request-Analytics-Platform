import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from accounts.mongo import db
from accounts.documents import UserDocument



class JWTAuthentication(authentication.BaseAuthentication):

	def authenticate(self, request):
		auth_header = request.headers.get('Authorization')
		if not auth_header:
			return None

		parts = auth_header.split()

		if len(parts) != 2 or parts[0].lower() != "bearer":
			raise AuthenticationFailed("Invalid authentication header")

		token = parts[1]
		try:
			payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
		except jwt.ExpiredSignatureError:
			raise AuthenticationFailed("Token has expired")
		except jwt.InvalidTokenError:
			raise AuthenticationFailed("Invalid token")


		if payload.get('type') != "access":
			raise AuthenticationFailed("Access token required")

		user_id = payload.get("user_id")
		user = db[UserDocument.collection_name].find_one({"id": user_id})

		if not user:
			raise AuthenticationFailed("User not found")

		if not user.get("is_active", False):
			raise AuthenticationFailed("User account is inactive")

		return (MongoUser(user), token)

class MongoUser:

	def __init__(self, user):
		self.id=user["id"]
		self.username=user["username"]
		self.email=user["email"]
		self.role=user["role"]
		self.is_active=user["is_active"]

	@property
	def is_authenticated(self):
		return True
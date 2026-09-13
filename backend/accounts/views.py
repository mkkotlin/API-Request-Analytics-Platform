from django. contrib.auth.hashers import make_password, check_password
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import datetime, timezone
from accounts.mongo import db
from accounts.documents import UserDocument
from accounts.serializers import RegisterSerializer, LoginSerializer, RefreshTokenSerializer
from accounts.jwt import create_access_token, create_refresh_token
from rest_framework.permissions import IsAuthenticated
from accounts.jwt import create_access_token
import jwt
from config import settings
from accounts.documents import UserDocument, RefreshTokenDocument

# Create your views here.

class RegisterView(APIView):
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        users = db[UserDocument.collection_name]

        if users.find_one({"email":data["email"]}):
            return Response({"detail": "Email already exists"}, status=status.HTTP_409_CONFLICT)

        if users.find_one({"username":data["username"]}):
            return Response({"detail": "Username already exists"}, status=status.HTTP_409_CONFLICT)

        user = UserDocument.create(username=data["username"], email=data["email"], password_hash=make_password(data["password"]))
        users.insert_one(user)
        return Response(
            {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"]
            }
            )

class LoginView(APIView):

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        users = db[UserDocument.collection_name]
        user = users.find_one({"email":data["email"]})

        if not user:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_403_FORBIDDEN
                )

        if not check_password(data["password"], user["password"]):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        refresh_payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        refresh_tokens_collection = db[RefreshTokenDocument.collection_name]
        refresh_tokens_collection.insert_one(RefreshTokenDocument.create(user_id=user["id"], jti=refresh_payload["jti"], expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz = timezone.utc)))
        return Response({"access": access_token, "refresh": refresh_token})



class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "role": request.user.role,
            })


class RefreshTokenView(APIView):

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        refresh_token = serializer.validated_data["refresh"]

        try:
            payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return Response({"detail":"Refesh token has expired"}, status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({"detail":"Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        if payload.get("type") != "refresh":
            return Response({"detail":"Refesh token required"}, status=status.HTTP_401_UNAUTHORIZED)

        jti = payload.get("jti")
        user_id = payload.get("user_id")
        refresh_token_doc = db[RefreshTokenDocument.collection_name].find_one({
            "jti": jti,
            "user_id": user_id,
            "revoked": False
            })

        if not refresh_token_doc:
            return Response({"detail": "Refresh token has been revoked"}, status=status.HTTP_401_UNAUTHORIZED)

        user = db[UserDocument.collection_name].find_one({
            "id": user_id
            })

        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.get("is_active", False):
            return Response({"detail":"User account is inactive"}, status=status.HTTP_403_FORBIDDEN)


        access_token = create_access_token(user)
        return Response({"access":access_token})



class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"detail":"Refesh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return Response({"detail":"Invalid refresh token"}, status=status.HTTP_400_BAD_REQUEST)


        if payload.get("type") != "refresh":
            return Response({"detail":"Refesh token required"}, status=status.HTTP_400_BAD_REQUEST)

        db[RefreshTokenDocument.collection_name].update_one(
            {
            "jti":payload.get("jti"),
            "user_id": request.user.id
            }, 
            {
            "$set":{
            "revoked":True
            }
            }
            )
        return Response({"detail":"Logged out successfully"}, status=status.HTTP_200_OK)
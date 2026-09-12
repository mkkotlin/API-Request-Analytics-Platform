from django. contrib.auth.hashers import make_password, check_password
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mongo import db
from accounts.documents import UserDocument
from accounts.serializers import RegisterSerializer, LoginSerializer
from accounts.jwt import create_access_token, create_refresh_token
from rest_framework.permissions import IsAuthenticated

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

        return Response({"access": access_token, "refresh":refresh_token})



class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "role": request.user.role,
            })
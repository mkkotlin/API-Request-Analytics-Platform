r"""
===================================================================
How to run these tests in your terminal:
===================================================================

PowerShell / Windows Terminal (using project venv):
    & "I:\API Request Analytics Platform\backend\apienv\Scripts\python.exe" manage.py test accounts -v 2

Standard Python (if virtual environment is active):
    python manage.py test accounts -v 2

===================================================================
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.hashers import make_password
from accounts.mongo import db
from accounts.documents import UserDocument


class AccountsAPITestCase(APITestCase):

    def setUp(self):
        self.test_email = "mayank@gmail.com"
        self.test_password = "Password123"
        self.test_username = "mayank"

        # Ensure user exists in MongoDB database for login test
        users_col = db[UserDocument.collection_name]
        user = users_col.find_one({"email": self.test_email})
        if not user:
            new_user = UserDocument.create(
                username=self.test_username,
                email=self.test_email,
                password_hash=make_password(self.test_password)
            )
            users_col.insert_one(new_user)

    def test_register_and_cleanup_user(self):
        print("\n" + "=" * 60)
        print("  RUNNING REGISTER ENDPOINT TEST WITH BATMAN & CLEANUP BY ID")
        print("=" * 60)

        users_col = db[UserDocument.collection_name]
        # Pre-cleanup in case batman already exists in MongoDB
        users_col.delete_many({"email": "batman@gmail.com"})
        users_col.delete_many({"username": "batman"})

        reg_payload = {
            "username": "batman",
            "email": "batman@gmail.com",
            "password": "Password123"
        }

        created_user_id = None
        try:
            print(f"\n[1] POST /api/auth/register/")
            print(f"    Payload Sent  : {reg_payload}")
            res_reg = self.client.post('/api/auth/register/', reg_payload, format='json')
            print(f"    Status Code   : {res_reg.status_code}")
            print(f"    Response Keys : {list(res_reg.data.keys()) if isinstance(res_reg.data, dict) else type(res_reg.data)}")
            print(f"    Response Data : {res_reg.data}")
            self.assertEqual(res_reg.status_code, status.HTTP_200_OK)

            created_user_id = res_reg.data.get("id")
            print(f"    Created User ID : {created_user_id}")
            self.assertIsNotNone(created_user_id)
        finally:
            if created_user_id:
                delete_result = users_col.delete_one({"id": created_user_id})
                print(f"\n[CLEANUP] Deleted user ID '{created_user_id}' from MongoDB. Deleted count: {delete_result.deleted_count}")

        print("\n" + "=" * 60)
        print("  REGISTER TEST AND ID CLEANUP COMPLETED SUCCESSFULLY")
        print("=" * 60 + "\n")

    def test_auth_endpoints_except_register(self):
        print("\n" + "=" * 60)
        print("  RUNNING AUTHENTICATION ENDPOINTS TEST (EXCEPT REGISTER)")
        print(f"  Credentials: email='{self.test_email}', password='{self.test_password}'")
        print("=" * 60)

        # 1. LOGIN
        login_payload = {
            "email": self.test_email,
            "password": self.test_password
        }
        print(f"\n[1] POST /api/auth/login/")
        print(f"    Payload Sent  : {login_payload}")
        res_login = self.client.post('/api/auth/login/', login_payload, format='json')
        print(f"    Status Code   : {res_login.status_code}")
        print(f"    Response Keys : {list(res_login.data.keys()) if isinstance(res_login.data, dict) else type(res_login.data)}")
        print(f"    Response Data : {res_login.data}")
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)

        access_token = res_login.data.get("access")
        refresh_token = res_login.data.get("refresh")
        self.assertIsNotNone(access_token)
        self.assertIsNotNone(refresh_token)

        # 2. GET /api/auth/me/ (AUTHENTICATED USER PROFILE)
        print(f"\n[2] GET /api/auth/me/")
        print(f"    Header Sent   : Authorization: Bearer {access_token[:25]}...")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        res_me = self.client.get('/api/auth/me/')
        print(f"    Status Code   : {res_me.status_code}")
        print(f"    Response Keys : {list(res_me.data.keys()) if isinstance(res_me.data, dict) else type(res_me.data)}")
        print(f"    Response Data : {res_me.data}")
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)

        # 3. POST /api/auth/refresh/ (TOKEN REFRESH)
        print(f"\n[3] POST /api/auth/refresh/")
        print(f"    Payload Sent  : {{'refresh': '{refresh_token[:25]}...'}}")
        self.client.credentials()  # Clear authorization header
        res_refresh = self.client.post('/api/auth/refresh/', {"refresh": refresh_token}, format='json')
        print(f"    Status Code   : {res_refresh.status_code}")
        print(f"    Response Keys : {list(res_refresh.data.keys()) if isinstance(res_refresh.data, dict) else type(res_refresh.data)}")
        print(f"    Response Data : {res_refresh.data}")
        self.assertEqual(res_refresh.status_code, status.HTTP_200_OK)

        # 4. POST /api/auth/logout/ (LOGOUT)
        print(f"\n[4] POST /api/auth/logout/")
        print(f"    Header Sent   : Authorization: Bearer {access_token[:25]}...")
        print(f"    Payload Sent  : {{'refresh': '{refresh_token[:25]}...'}}")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        res_logout = self.client.post('/api/auth/logout/', {"refresh": refresh_token}, format='json')
        print(f"    Status Code   : {res_logout.status_code}")
        print(f"    Response Keys : {list(res_logout.data.keys()) if isinstance(res_logout.data, dict) else type(res_logout.data)}")
        print(f"    Response Data : {res_logout.data}")
        self.assertEqual(res_logout.status_code, status.HTTP_200_OK)

        # 5. VERIFY REVOKED TOKEN CANNOT BE REFRESHED
        print(f"\n[5] POST /api/auth/refresh/ (Testing Revoked Token)")
        print(f"    Payload Sent  : {{'refresh': '{refresh_token[:25]}...'}}")
        self.client.credentials()
        res_revoked = self.client.post('/api/auth/refresh/', {"refresh": refresh_token}, format='json')
        print(f"    Status Code   : {res_revoked.status_code}")
        print(f"    Response Keys : {list(res_revoked.data.keys()) if isinstance(res_revoked.data, dict) else type(res_revoked.data)}")
        print(f"    Response Data : {res_revoked.data}")
        self.assertEqual(res_revoked.status_code, status.HTTP_401_UNAUTHORIZED)

        # SUMMARY OUTPUT
        print("\n" + "=" * 60)
        print("  SUMMARY OF TEST RESULTS")
        print("=" * 60)
        print(f"  1. Login   (/api/auth/login/)   : Status {res_login.status_code} {'PASS' if res_login.status_code == status.HTTP_200_OK else 'FAIL'}")
        print(f"  2. Me      (/api/auth/me/)      : Status {res_me.status_code} {'PASS' if res_me.status_code == status.HTTP_200_OK else 'FAIL'}")
        print(f"  3. Refresh (/api/auth/refresh/) : Status {res_refresh.status_code} {'PASS' if res_refresh.status_code == status.HTTP_200_OK else 'FAIL'}")
        print(f"  4. Logout  (/api/auth/logout/)  : Status {res_logout.status_code} {'PASS' if res_logout.status_code == status.HTTP_200_OK else 'FAIL'}")
        print(f"  5. Revoked (/api/auth/refresh/) : Status {res_revoked.status_code} {'PASS' if res_revoked.status_code == status.HTTP_401_UNAUTHORIZED else 'FAIL'}")
        print("=" * 60 + "\n")

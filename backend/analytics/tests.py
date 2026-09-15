from datetime import datetime, timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from accounts.mongo import db
from accounts.documents import UserDocument
from accounts.jwt import create_access_token
from analytics.documents import APIRequestDocument


class AnalyticsMiddlewareTestCase(APITestCase):

    def test_query_parameters_logging(self):
        # Call GET with query parameters
        response = self.client.get('/api/projects/?status=active&page=2')
        
        # Check X-Request-ID header
        self.assertIn('X-Request-ID', response)
        request_id = response['X-Request-ID']
        
        # Verify MongoDB recorded the request with correct query_string and request_id
        doc = db[APIRequestDocument.collection_name].find_one({"request_id": request_id})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["endpoint"], "/api/projects/")
        self.assertEqual(doc["query_string"], "status=active&page=2")
        self.assertEqual(doc["request_id"], request_id)
        self.assertIn("response_time_ms", doc)
        self.assertIsNotNone(doc["timestamp"])

    def test_404_error_logging(self):
        # Call non-existent endpoint
        response = self.client.get('/api/something-that-does-not-exist/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Check X-Request-ID header
        self.assertIn('X-Request-ID', response)
        request_id = response['X-Request-ID']
        
        # Verify MongoDB recorded 404 status code and endpoint
        doc = db[APIRequestDocument.collection_name].find_one({"request_id": request_id})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["endpoint"], "/api/something-that-does-not-exist/")
        self.assertEqual(doc["status_code"], 404)
        self.assertIsInstance(doc["response_time_ms"], float)


class AnalyticsSummaryViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_default_behavior(self):
        response = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertIn("start", response.data["period"])
        self.assertIn("end", response.data["period"])
        self.assertIn("total_requests", response.data)

    def test_custom_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        dt_outside = datetime.fromisoformat("2026-09-11T12:00:00+00:00")

        doc_inside = APIRequestDocument.create(
            request_id="req1",
            method="GET",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=50.0,
            timestamp=dt_inside,
            user_id=self.user["id"]
        )

        doc_outside = APIRequestDocument.create(
            request_id="req2",
            method="GET",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=50.0,
            timestamp=dt_outside,
            user_id=self.user["id"]
        )

        db[APIRequestDocument.collection_name].insert_many([doc_inside, doc_outside])

        response = self.client.get('/api/v1/analytics/summary/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_requests"], 1)

    def test_invalid_range(self):
        response = self.client.get('/api/v1/analytics/summary/?from=2026-09-14T00:00:00Z&to=2026-09-13T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' must be earlier than 'to'.")

    def test_invalid_format(self):
        response = self.client.get('/api/v1/analytics/summary/?from=hello&to=world')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "Invalid date format. Use ISO-8601 format.")


class EndpointAnalyticsViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_endpoints_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id=f"req_{i}",
                method="GET" if i < 3 else "POST",
                endpoint="/api/auth/me/" if i < 3 else "/api/auth/refresh/",
                status_code=200,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            )
            for i in range(4)
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/endpoints/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertEqual(response.data["limit"], 10)
        self.assertEqual(len(response.data["endpoints"]), 2)
        self.assertEqual(response.data["endpoints"][0]["endpoint"], "/api/auth/me/")
        self.assertEqual(response.data["endpoints"][0]["request_count"], 3)

    def test_endpoints_custom_limit(self):
        response = self.client.get('/api/v1/analytics/endpoints/?limit=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["limit"], 5)

    def test_endpoints_invalid_limit(self):
        res1 = self.client.get('/api/v1/analytics/endpoints/?limit=abc')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res1.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(res1.data["error"]["message"], "'limit' must be an integer.")

        res2 = self.client.get('/api/v1/analytics/endpoints/?limit=0')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res2.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(res2.data["error"]["message"], "'limit' must be between 1 and 100.")

        res3 = self.client.get('/api/v1/analytics/endpoints/?limit=101')
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res3.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(res3.data["error"]["message"], "'limit' must be between 1 and 100.")

    def test_endpoints_date_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        doc = APIRequestDocument.create(
            request_id="req_dt",
            method="GET",
            endpoint="/api/auth/me/",
            status_code=200,
            response_time_ms=10.0,
            timestamp=dt_inside,
            user_id=self.user["id"]
        )
        db[APIRequestDocument.collection_name].insert_one(doc)

        response = self.client.get('/api/v1/analytics/endpoints/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["endpoints"]), 1)


class StatusCodeAnalyticsViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_status_codes_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id="sc_1",
                method="GET",
                endpoint="/api/test/",
                status_code=200,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="sc_2",
                method="GET",
                endpoint="/api/test/",
                status_code=200,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="sc_3",
                method="GET",
                endpoint="/api/test/",
                status_code=400,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="sc_4",
                method="GET",
                endpoint="/api/test/",
                status_code=500,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            )
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/status-codes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertEqual(len(response.data["status_codes"]), 3)
        self.assertEqual(response.data["status_codes"][0]["status_code"], 200)
        self.assertEqual(response.data["status_codes"][0]["request_count"], 2)
        self.assertEqual(response.data["status_codes"][1]["status_code"], 400)
        self.assertEqual(response.data["status_codes"][1]["request_count"], 1)

    def test_status_codes_date_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        doc = APIRequestDocument.create(
            request_id="sc_dt",
            method="GET",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=10.0,
            timestamp=dt_inside,
            user_id=self.user["id"]
        )
        db[APIRequestDocument.collection_name].insert_one(doc)

        response = self.client.get('/api/v1/analytics/status-codes/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["status_codes"]), 1)
        self.assertEqual(response.data["status_codes"][0]["status_code"], 200)
        self.assertEqual(response.data["status_codes"][0]["request_count"], 1)

    def test_status_codes_invalid_date_range(self):
        response = self.client.get('/api/v1/analytics/status-codes/?from=2026-09-14T00:00:00Z&to=2026-09-13T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' must be earlier than 'to'.")


class ResponseTimeAnalyticsViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_response_times_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id="rt_1",
                method="GET",
                endpoint="/api/slow-endpoint/",
                status_code=200,
                response_time_ms=100.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="rt_2",
                method="GET",
                endpoint="/api/fast-endpoint/",
                status_code=200,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            )
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/response-times/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertEqual(response.data["overall"]["request_count"], 2)
        self.assertEqual(response.data["overall"]["average_ms"], 55.0)
        self.assertEqual(response.data["overall"]["minimum_ms"], 10.0)
        self.assertEqual(response.data["overall"]["maximum_ms"], 100.0)
        self.assertEqual(len(response.data["slowest_endpoints"]), 2)
        self.assertEqual(response.data["slowest_endpoints"][0]["endpoint"], "/api/slow-endpoint/")

    def test_response_times_empty_results(self):
        response = self.client.get('/api/v1/analytics/response-times/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall"]["request_count"], 0)
        self.assertEqual(response.data["overall"]["average_ms"], 0)
        self.assertEqual(response.data["slowest_endpoints"], [])

    def test_response_times_date_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        doc = APIRequestDocument.create(
            request_id="rt_dt",
            method="GET",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=45.0,
            timestamp=dt_inside,
            user_id=self.user["id"]
        )
        db[APIRequestDocument.collection_name].insert_one(doc)

        response = self.client.get('/api/v1/analytics/response-times/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall"]["request_count"], 1)
        self.assertEqual(response.data["overall"]["average_ms"], 45.0)

    def test_response_times_invalid_range(self):
        response = self.client.get('/api/v1/analytics/response-times/?from=2026-09-14T00:00:00Z&to=2026-09-13T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' must be earlier than 'to'.")


class UserAnalyticsViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "user_abc_123",
            "username": "user1",
            "email": "user1@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_users_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id="u_1",
                method="GET",
                endpoint="/api/test/",
                status_code=200,
                response_time_ms=30.0,
                timestamp=now,
                user_id=self.user["id"],
                user_role=self.user["role"]
            ),
            APIRequestDocument.create(
                request_id="u_2",
                method="GET",
                endpoint="/api/test/",
                status_code=200,
                response_time_ms=50.0,
                timestamp=now,
                user_id=self.user["id"],
                user_role=self.user["role"]
            )
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertEqual(len(response.data["users"]), 1)
        self.assertEqual(response.data["users"][0]["user_id"], self.user["id"])
        self.assertEqual(response.data["users"][0]["role"], "admin")
        self.assertEqual(response.data["users"][0]["request_count"], 2)
        self.assertEqual(response.data["users"][0]["average_response_time_ms"], 40.0)

    def test_users_ignores_anonymous(self):
        now = datetime.now(timezone.utc)
        anon_doc = APIRequestDocument.create(
            request_id="u_anon",
            method="GET",
            endpoint="/api/public/",
            status_code=200,
            response_time_ms=15.0,
            timestamp=now,
            user_id=None,
            user_role=None
        )
        db[APIRequestDocument.collection_name].insert_one(anon_doc)

        response = self.client.get('/api/v1/analytics/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["users"]), 0)

    def test_users_date_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        doc = APIRequestDocument.create(
            request_id="u_dt",
            method="GET",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=25.0,
            timestamp=dt_inside,
            user_id=self.user["id"],
            user_role=self.user["role"]
        )
        db[APIRequestDocument.collection_name].insert_one(doc)

        response = self.client.get('/api/v1/analytics/users/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["users"]), 1)

    def test_users_invalid_range(self):
        response = self.client.get('/api/v1/analytics/users/?from=2026-09-14T00:00:00Z&to=2026-09-13T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' must be earlier than 'to'.")


class ErrorAnalyticsViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_errors_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id="err_1",
                method="GET",
                endpoint="/api/bad/",
                status_code=404,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="err_2",
                method="GET",
                endpoint="/api/good/",
                status_code=200,
                response_time_ms=10.0,
                timestamp=now,
                user_id=self.user["id"]
            )
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/errors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertEqual(response.data["errors"][0]["endpoint"], "/api/bad/")
        self.assertEqual(response.data["errors"][0]["status_code"], 404)


class MethodAnalyticsViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_methods_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id="m_1",
                method="GET",
                endpoint="/api/test/",
                status_code=200,
                response_time_ms=30.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="m_2",
                method="GET",
                endpoint="/api/test/",
                status_code=200,
                response_time_ms=32.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="m_3",
                method="POST",
                endpoint="/api/test/",
                status_code=201,
                response_time_ms=45.0,
                timestamp=now,
                user_id=self.user["id"]
            )
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/methods/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertEqual(len(response.data["methods"]), 2)
        self.assertEqual(response.data["methods"][0]["method"], "GET")
        self.assertEqual(response.data["methods"][0]["request_count"], 2)
        self.assertEqual(response.data["methods"][0]["average_response_time_ms"], 31.0)
        self.assertEqual(response.data["methods"][1]["method"], "POST")
        self.assertEqual(response.data["methods"][1]["request_count"], 1)

    def test_methods_date_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        doc = APIRequestDocument.create(
            request_id="m_dt",
            method="PUT",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=20.0,
            timestamp=dt_inside,
            user_id=self.user["id"]
        )
        db[APIRequestDocument.collection_name].insert_one(doc)

        response = self.client.get('/api/v1/analytics/methods/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["methods"]), 1)
        self.assertEqual(response.data["methods"][0]["method"], "PUT")

    def test_methods_invalid_range(self):
        response = self.client.get('/api/v1/analytics/methods/?from=2026-09-14T00:00:00Z&to=2026-09-13T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' must be earlier than 'to'.")


class AnalyticsDashboardViewTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "role": "admin"
        }
        self.token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        db[UserDocument.collection_name].insert_one({
            "id": self.user["id"],
            "username": self.user["username"],
            "email": self.user["email"],
            "role": self.user["role"],
            "is_active": True
        })

    def tearDown(self):
        db[UserDocument.collection_name].delete_many({"id": self.user["id"]})
        db[APIRequestDocument.collection_name].delete_many({})

    def test_dashboard_default_behavior(self):
        now = datetime.now(timezone.utc)
        docs = [
            APIRequestDocument.create(
                request_id="dash_1",
                method="GET",
                endpoint="/api/auth/me/",
                status_code=200,
                response_time_ms=20.0,
                timestamp=now,
                user_id=self.user["id"]
            ),
            APIRequestDocument.create(
                request_id="dash_2",
                method="POST",
                endpoint="/api/auth/refresh/",
                status_code=400,
                response_time_ms=40.0,
                timestamp=now,
                user_id=self.user["id"]
            )
        ]
        db[APIRequestDocument.collection_name].insert_many(docs)

        response = self.client.get('/api/v1/analytics/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("period", response.data)
        self.assertIn("summary", response.data)
        self.assertEqual(response.data["summary"]["total_requests"], 2)
        self.assertEqual(response.data["summary"]["successful_requests"], 1)
        self.assertEqual(response.data["summary"]["client_errors"], 1)
        self.assertEqual(len(response.data["top_endpoints"]), 2)
        self.assertEqual(len(response.data["methods"]), 2)
        self.assertEqual(len(response.data["status_codes"]), 2)

    def test_dashboard_empty_results(self):
        response = self.client.get('/api/v1/analytics/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["total_requests"], 0)
        self.assertEqual(response.data["top_endpoints"], [])
        self.assertEqual(response.data["methods"], [])
        self.assertEqual(response.data["status_codes"], [])

    def test_dashboard_date_range(self):
        dt_inside = datetime.fromisoformat("2026-09-13T12:00:00+00:00")
        doc = APIRequestDocument.create(
            request_id="dash_dt",
            method="GET",
            endpoint="/api/test/",
            status_code=200,
            response_time_ms=15.0,
            timestamp=dt_inside,
            user_id=self.user["id"]
        )
        db[APIRequestDocument.collection_name].insert_one(doc)

        response = self.client.get('/api/v1/analytics/dashboard/?from=2026-09-13T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["total_requests"], 1)

    def test_dashboard_invalid_range(self):
        response = self.client.get('/api/v1/analytics/dashboard/?from=2026-09-14T00:00:00Z&to=2026-09-13T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' must be earlier than 'to'.")

    def test_dashboard_excessive_range(self):
        response = self.client.get('/api/v1/analytics/dashboard/?from=2026-01-01T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "Analytics date range cannot exceed 31 days.")

    def test_dashboard_incomplete_range(self):
        response = self.client.get('/api/v1/analytics/dashboard/?from=2026-09-01T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "'from' and 'to' must be provided together.")

    def test_dashboard_valid_range(self):
        response = self.client.get('/api/v1/analytics/dashboard/?from=2026-09-01T00:00:00Z&to=2026-09-14T00:00:00Z')
        self.assertEqual(response.status_code, status.HTTP_200_OK)









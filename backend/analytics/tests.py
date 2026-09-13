from rest_framework.test import APITestCase
from rest_framework import status
from accounts.mongo import db
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


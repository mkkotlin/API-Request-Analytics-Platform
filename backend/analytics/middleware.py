import time
from uuid import uuid4
from datetime import datetime, timezone

from .documents import APIRequestDocument
from accounts.mongo import db


class APIRequestTrackingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request_id = str(uuid4())

        request.request_id = request_id

        start_time = time.perf_counter()

        exception = None

        try:
            response = self.get_response(request)

        except Exception as exc:
            exception = exc
            raise

        finally:
            elapsed = time.perf_counter() - start_time

            response_time_ms = round(
                elapsed * 1000,
                2
            )

            self._record_request(
                request,
                response if "response" in locals() else None,
                request_id,
                response_time_ms,
                exception
            )

        if response:
            response["X-Request-ID"] = request_id

        return response

    def _record_request(
        self,
        request,
        response,
        request_id,
        response_time_ms,
        exception
    ):

        user_id = None
        user_role = None

        if (
            hasattr(request, "user")
            and request.user.is_authenticated
        ):
            user_id = request.user.id
            user_role = request.user.role

        document = APIRequestDocument.create(
            request_id=request_id,
            method=request.method,
            endpoint=request.path,
            status_code=(
                response.status_code
                if response
                else 500
            ),
            response_time_ms=response_time_ms,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            user_role=user_role,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get(
                "HTTP_USER_AGENT"
            ),
            query_string=request.META.get(
                "QUERY_STRING"
            ),
            protocol=request.META.get(
                "SERVER_PROTOCOL"
            ),
            request_content_type=request.META.get(
                "CONTENT_TYPE"
            ),
            response_content_type=(
                response.get("Content-Type")
                if response
                else None
            ),
            error=str(exception) if exception else None,
        )

        db[
            APIRequestDocument.collection_name
        ].insert_one(document)

    @staticmethod
    def _get_client_ip(request):

        forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        return request.META.get("REMOTE_ADDR")
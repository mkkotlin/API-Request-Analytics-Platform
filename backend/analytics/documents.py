class APIRequestDocument:

    collection_name = "api_requests"

    @staticmethod
    def create(
        request_id,
        method,
        endpoint,
        status_code,
        response_time_ms,
        timestamp,
        user_id=None,
        user_role=None,
        ip_address=None,
        user_agent=None,
        query_string=None,
        protocol=None,
        request_content_type=None,
        response_content_type=None,
        error=None,
    ):
        return {
            "request_id": request_id,
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "query_string": query_string,
            "protocol": protocol,
            "request_content_type": request_content_type,
            "response_content_type": response_content_type,
            "error": error,
        }
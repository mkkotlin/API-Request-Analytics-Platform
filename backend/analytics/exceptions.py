from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    request = context.get("request")

    request_id = getattr(
        request,
        "request_id",
        None
    )

    detail = response.data

    if isinstance(detail, dict) and "detail" in detail:
        message = detail["detail"]
        details = {}
    else:
        message = "Request validation failed."
        details = detail

    if response.status_code == 400:
        code = "VALIDATION_ERROR"
    elif response.status_code == 401:
        code = "AUTHENTICATION_ERROR"
    elif response.status_code == 403:
        code = "PERMISSION_DENIED"
    elif response.status_code == 404:
        code = "NOT_FOUND"
    elif response.status_code == 429:
        code = "RATE_LIMIT_EXCEEDED"
    elif response.status_code >= 500:
        code = "SERVER_ERROR"
    else:
        code = "API_ERROR"

    response.data = {
        "error": {
            "code": code,
            "message": str(message),
            "details": details,
            "request_id": request_id,
        }
    }

    if request_id:
        response["X-Request-ID"] = request_id

    return response

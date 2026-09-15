from datetime import datetime, timezone, timedelta
from rest_framework.response import Response


MAX_ANALYTICS_RANGE = timedelta(days=31)


def parse_datetime(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:
        return None


def get_analytics_date_range(request):
    now = datetime.now(timezone.utc)

    from_value = request.query_params.get("from")
    to_value = request.query_params.get("to")

    if not from_value and not to_value:
        return (
            now - timedelta(hours=24),
            now,
            None
        )

    if not from_value or not to_value:
        return (
            None,
            None,
            "'from' and 'to' must be provided together."
        )

    start_time = parse_datetime(from_value)
    end_time = parse_datetime(to_value)

    if not start_time or not end_time:
        return (
            None,
            None,
            "Invalid date format. Use ISO-8601 format."
        )

    if start_time >= end_time:
        return (
            None,
            None,
            "'from' must be earlier than 'to'."
        )

    if end_time - start_time > MAX_ANALYTICS_RANGE:
        return (
            None,
            None,
            "Analytics date range cannot exceed 31 days."
        )

    return start_time, end_time, None


def error_response(
    code,
    message,
    details=None,
    status=400,
    request_id=None,
):
    response = Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        },
        status=status,
    )

    if request_id:
        response["X-Request-ID"] = request_id

    return response

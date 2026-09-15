import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mongo import db
from analytics.documents import APIRequestDocument
from analytics.permissions import IsAnalyticsAdmin
from analytics.throttles import AnalyticsRateThrottle
from .utils import (
    get_analytics_date_range,
    error_response,
)

logger = logging.getLogger(__name__)


class AnalyticsSummaryView(APIView):

    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):

        collection = db[
            APIRequestDocument.collection_name
        ]

        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": None,

                    "total_requests": {
                        "$sum": 1
                    },

                    "successful_requests": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$gte": [
                                        "$status_code",
                                        200
                                    ]
                                },
                                {
                                    "$cond": [
                                        {
                                            "$lt": [
                                                "$status_code",
                                                300
                                            ]
                                        },
                                        1,
                                        0
                                    ]
                                },
                                0
                            ]
                        }
                    },

                    "client_errors": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {
                                            "$gte": [
                                                "$status_code",
                                                400
                                            ]
                                        },
                                        {
                                            "$lt": [
                                                "$status_code",
                                                500
                                            ]
                                        }
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    },

                    "server_errors": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$gte": [
                                        "$status_code",
                                        500
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    },

                    "average_response_time_ms": {
                        "$avg": "$response_time_ms"
                    }
                }
            }
        ]

        result = list(
            collection.aggregate(pipeline)
        )

        if not result:
            return Response({
                "period": {
                    "start": start_time,
                    "end": end_time
                },
                "total_requests": 0,
                "successful_requests": 0,
                "client_errors": 0,
                "server_errors": 0,
                "average_response_time_ms": 0
            })

        data = result[0]

        return Response({
            "period": {
                "start": start_time,
                "end": end_time
            },
            "total_requests": data["total_requests"],
            "successful_requests": data["successful_requests"],
            "client_errors": data["client_errors"],
            "server_errors": data["server_errors"],
            "average_response_time_ms": round(
                data["average_response_time_ms"],
                2
            )
        })


class EndpointAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        limit_value = request.query_params.get("limit", "10")

        # Parse limit
        try:
            limit = int(limit_value)
        except ValueError:
            return error_response(
                code="VALIDATION_ERROR",
                message="'limit' must be an integer.",
                request_id=getattr(request, "request_id", None),
            )

        if limit < 1 or limit > 100:
            return error_response(
                code="VALIDATION_ERROR",
                message="'limit' must be between 1 and 100.",
                request_id=getattr(request, "request_id", None),
            )

        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "method": "$method",
                        "endpoint": "$endpoint",
                    },
                    "request_count": {
                        "$sum": 1
                    },
                }
            },
            {
                "$sort": {
                    "request_count": -1
                }
            },
            {
                "$limit": limit
            },
        ]

        results = list(
            db[APIRequestDocument.collection_name].aggregate(
                pipeline
            )
        )

        endpoints = [
            {
                "method": item["_id"]["method"],
                "endpoint": item["_id"]["endpoint"],
                "request_count": item["request_count"],
            }
            for item in results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "limit": limit,
                "endpoints": endpoints,
            }
        )


class StatusCodeAnalyticsView(APIView):
    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    }
                }
            },
            {
                "$group": {
                    "_id": "$status_code",
                    "request_count": {
                        "$sum": 1
                    },
                }
            },
            {
                "$sort": {
                    "_id": 1
                }
            },
        ]

        results = list(
            db[APIRequestDocument.collection_name].aggregate(
                pipeline
            )
        )

        status_codes = [
            {
                "status_code": item["_id"],
                "request_count": item["request_count"],
            }
            for item in results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "status_codes": status_codes,
            }
        )


class ResponseTimeAnalyticsView(APIView):
    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        collection = db[APIRequestDocument.collection_name]

        # Overall response-time statistics
        overall_pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "average_ms": {
                        "$avg": "$response_time_ms"
                    },
                    "minimum_ms": {
                        "$min": "$response_time_ms"
                    },
                    "maximum_ms": {
                        "$max": "$response_time_ms"
                    },
                    "request_count": {
                        "$sum": 1
                    },
                }
            }
        ]

        overall_result = list(
            collection.aggregate(overall_pipeline)
        )

        if overall_result:
            overall = overall_result[0]

            overall_stats = {
                "request_count": overall["request_count"],
                "average_ms": round(
                    overall["average_ms"], 2
                ),
                "minimum_ms": round(
                    overall["minimum_ms"], 2
                ),
                "maximum_ms": round(
                    overall["maximum_ms"], 2
                ),
            }
        else:
            overall_stats = {
                "request_count": 0,
                "average_ms": 0,
                "minimum_ms": 0,
                "maximum_ms": 0,
            }

        # Slowest endpoints
        endpoint_pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "method": "$method",
                        "endpoint": "$endpoint",
                    },
                    "average_ms": {
                        "$avg": "$response_time_ms"
                    },
                    "maximum_ms": {
                        "$max": "$response_time_ms"
                    },
                    "request_count": {
                        "$sum": 1
                    },
                }
            },
            {
                "$sort": {
                    "average_ms": -1
                }
            },
            {
                "$limit": 10
            },
        ]

        endpoint_results = list(
            collection.aggregate(endpoint_pipeline)
        )

        slowest_endpoints = [
            {
                "method": item["_id"]["method"],
                "endpoint": item["_id"]["endpoint"],
                "request_count": item["request_count"],
                "average_ms": round(
                    item["average_ms"], 2
                ),
                "maximum_ms": round(
                    item["maximum_ms"], 2
                ),
            }
            for item in endpoint_results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "overall": overall_stats,
                "slowest_endpoints": slowest_endpoints,
            }
        )


class UserAnalyticsView(APIView):
    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    },
                    "user_id": {
                        "$ne": None
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "user_id": "$user_id",
                        "user_role": "$user_role",
                    },
                    "request_count": {
                        "$sum": 1
                    },
                    "average_response_time_ms": {
                        "$avg": "$response_time_ms"
                    },
                }
            },
            {
                "$sort": {
                    "request_count": -1
                }
            },
            {
                "$limit": 20
            },
        ]

        results = list(
            db[APIRequestDocument.collection_name].aggregate(
                pipeline
            )
        )

        users = [
            {
                "user_id": item["_id"]["user_id"],
                "role": item["_id"]["user_role"],
                "request_count": item["request_count"],
                "average_response_time_ms": round(
                    item["average_response_time_ms"],
                    2
                ),
            }
            for item in results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "users": users,
            }
        )


class ErrorAnalyticsView(APIView):
    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    },
                    "status_code": {
                        "$gte": 400
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "method": "$method",
                        "endpoint": "$endpoint",
                        "status_code": "$status_code",
                    },
                    "error_count": {
                        "$sum": 1
                    },
                }
            },
            {
                "$sort": {
                    "error_count": -1
                }
            },
            {
                "$limit": 20
            }
        ]

        results = list(
            db[APIRequestDocument.collection_name].aggregate(
                pipeline
            )
        )

        errors = [
            {
                "method": item["_id"]["method"],
                "endpoint": item["_id"]["endpoint"],
                "status_code": item["_id"]["status_code"],
                "error_count": item["error_count"],
            }
            for item in results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "errors": errors,
            }
        )


class MethodAnalyticsView(APIView):
    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lt": end_time,
                    }
                }
            },
            {
                "$group": {
                    "_id": "$method",
                    "request_count": {
                        "$sum": 1
                    },
                    "average_response_time_ms": {
                        "$avg": "$response_time_ms"
                    }
                }
            },
            {
                "$sort": {
                    "request_count": -1
                }
            }
        ]

        results = list(
            db[APIRequestDocument.collection_name].aggregate(
                pipeline
            )
        )

        methods = [
            {
                "method": item["_id"],
                "request_count": item["request_count"],
                "average_response_time_ms": round(
                    item["average_response_time_ms"],
                    2
                ),
            }
            for item in results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "methods": methods,
            }
        )


class AnalyticsDashboardView(APIView):
    permission_classes = [IsAnalyticsAdmin]
    throttle_classes = [AnalyticsRateThrottle]

    def get(self, request):
        start_time, end_time, error = get_analytics_date_range(request)

        if error:
            logger.warning(
                "Invalid analytics date range",
                extra={
                    "request_id": getattr(request, "request_id", None),
                    "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                },
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=error,
                request_id=getattr(
                    request,
                    "request_id",
                    None
                ),
            )

        logger.info(
            "Analytics dashboard requested",
            extra={
                "request_id": getattr(request, "request_id", None),
                "user_id": str(getattr(request.user, "id", None) or (request.user.get("id") if isinstance(request.user, dict) else None)),
                "user_role": getattr(request.user, "role", None) or (request.user.get("role") if isinstance(request.user, dict) else None),
            },
        )

        collection = db[APIRequestDocument.collection_name]

        match_stage = {
            "$match": {
                "timestamp": {
                    "$gte": start_time,
                    "$lt": end_time,
                }
            }
        }

        # Overall summary
        summary_pipeline = [
            match_stage,
            {
                "$group": {
                    "_id": None,
                    "total_requests": {"$sum": 1},
                    "successful_requests": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {
                                            "$gte": [
                                                "$status_code",
                                                200
                                            ]
                                        },
                                        {
                                            "$lt": [
                                                "$status_code",
                                                300
                                            ]
                                        }
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    },
                    "client_errors": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {
                                            "$gte": [
                                                "$status_code",
                                                400
                                            ]
                                        },
                                        {
                                            "$lt": [
                                                "$status_code",
                                                500
                                            ]
                                        }
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    },
                    "server_errors": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$gte": [
                                        "$status_code",
                                        500
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    },
                    "average_response_time_ms": {
                        "$avg": "$response_time_ms"
                    }
                }
            }
        ]

        summary_result = list(
            collection.aggregate(summary_pipeline)
        )

        if summary_result:
            summary = summary_result[0]

            summary_data = {
                "total_requests": summary["total_requests"],
                "successful_requests": summary["successful_requests"],
                "client_errors": summary["client_errors"],
                "server_errors": summary["server_errors"],
                "average_response_time_ms": round(
                    summary["average_response_time_ms"],
                    2
                )
            }
        else:
            summary_data = {
                "total_requests": 0,
                "successful_requests": 0,
                "client_errors": 0,
                "server_errors": 0,
                "average_response_time_ms": 0
            }

        # Top endpoints
        endpoint_pipeline = [
            match_stage,
            {
                "$group": {
                    "_id": {
                        "method": "$method",
                        "endpoint": "$endpoint"
                    },
                    "request_count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "request_count": -1
                }
            },
            {
                "$limit": 10
            }
        ]

        endpoint_results = list(
            collection.aggregate(endpoint_pipeline)
        )

        top_endpoints = [
            {
                "method": item["_id"]["method"],
                "endpoint": item["_id"]["endpoint"],
                "request_count": item["request_count"]
            }
            for item in endpoint_results
        ]

        # HTTP methods
        method_pipeline = [
            match_stage,
            {
                "$group": {
                    "_id": "$method",
                    "request_count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "request_count": -1
                }
            }
        ]

        method_results = list(
            collection.aggregate(method_pipeline)
        )

        methods = [
            {
                "method": item["_id"],
                "request_count": item["request_count"]
            }
            for item in method_results
        ]

        # Status codes
        status_pipeline = [
            match_stage,
            {
                "$group": {
                    "_id": "$status_code",
                    "request_count": {"$sum": 1}
                }
            },
            {
                "$sort": {
                    "_id": 1
                }
            }
        ]

        status_results = list(
            collection.aggregate(status_pipeline)
        )

        status_codes = [
            {
                "status_code": item["_id"],
                "request_count": item["request_count"]
            }
            for item in status_results
        ]

        return Response(
            {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "summary": summary_data,
                "top_endpoints": top_endpoints,
                "methods": methods,
                "status_codes": status_codes
            }
        )
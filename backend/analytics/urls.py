from django.urls import path

from .views import (
    AnalyticsSummaryView,
    EndpointAnalyticsView,
    StatusCodeAnalyticsView,
    ResponseTimeAnalyticsView,
    UserAnalyticsView,
    ErrorAnalyticsView,
    MethodAnalyticsView,
    AnalyticsDashboardView,
)

urlpatterns = [
    path("summary/", AnalyticsSummaryView.as_view()),
    path("endpoints/", EndpointAnalyticsView.as_view()),
    path("status-codes/", StatusCodeAnalyticsView.as_view()),
    path(
        "response-times/",
        ResponseTimeAnalyticsView.as_view()
    ),
    path(
        "users/",
        UserAnalyticsView.as_view()
    ),
    path(
        "errors/",
        ErrorAnalyticsView.as_view()
    ),
    path(
        "methods/",
        MethodAnalyticsView.as_view()
    ),
    path(
        "dashboard/",
        AnalyticsDashboardView.as_view()
    ),
]
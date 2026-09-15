from rest_framework.permissions import BasePermission


class IsAnalyticsAdmin(BasePermission):
	message = "Admin access is required."

	def has_permission(self, request, view):
		return request.user and request.user.is_authenticated and str(getattr(request.user, "role", "")).upper() == "ADMIN"
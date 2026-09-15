from django.http import JsonResponse
from django.views import View

from accounts.mongo import db


class HealthCheckView(View):
    def get(self, request):
        return JsonResponse({
            "status": "ok",
        })


class ReadinessCheckView(View):
    def get(self, request):
        try:
            db.command("ping")

            return JsonResponse({
                "status": "ready",
                "dependencies": {
                    "mongodb": "ok",
                },
            })

        except Exception:
            return JsonResponse(
                {
                    "status": "not_ready",
                    "dependencies": {
                        "mongodb": "unavailable",
                    },
                },
                status=503,
            )

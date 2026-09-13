from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
from django.conf import settings



def create_access_token(user):
	now = datetime.now(timezone.utc)
	payload = {
		"type": "access",
		"user_id": user["id"],
		"role": user["role"],
		"iat": now,
		"exp": now + timedelta(minutes=settings.JWT_ACCESS_MINUTES),
	}

	return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(user):
	now = datetime.now(timezone.utc)
	payload = {
		"type": "refresh",
		"jti": str(uuid4()),
		"user_id": user["id"],
		"role": user["role"],
		"iat": now,
		"exp": now + timedelta(days=settings.JWT_REFRESH_DAYS),
	}

	return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
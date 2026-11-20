import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    def __init__(self, message, status_code=503):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def request_ai_service(method, path, *, params=None, payload=None, timeout=70):
    if not settings.AI_SERVICE_TOKEN:
        raise AIServiceError("AI service credentials are not configured")
    try:
        response = requests.request(
            method,
            f"{settings.AI_SERVICE_URL}{path}",
            headers={"X-Service-Token": settings.AI_SERVICE_TOKEN},
            params=params,
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.exception("AI service request failed")
        raise AIServiceError("AI service is unavailable") from exc

    if not response.ok:
        try:
            message = response.json().get("detail", "AI service request failed")
        except ValueError:
            message = "AI service request failed"
        raise AIServiceError(message, response.status_code)
    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceError("AI service returned an invalid response", 502) from exc

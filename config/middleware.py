"""Request log: one line per request in Render's logs, without personal data (#137).

gunicorn's own access log is off (render.yaml): it writes the User-Agent, the Referer and
every full path. This line has only what we chose (docs/specs/request-logging.md).
"""

import logging
import time

from django.urls import Resolver404, resolve

logger = logging.getLogger(__name__)

# URL names whose path holds a secret: the pattern is logged instead (D3).
# password_reset_confirm: the uid and token from the reset email, and Django's redirect
# to …/set-password/ (same URL name).
SECRET_URL_NAMES = {"password_reset_confirm"}


class RequestLogMiddleware:
    """Log "<METHOD> <path> <status> <ms>ms" after each response, e.g. "GET / 200 35ms".

    Added in production.py only, right after WhiteNoise, so static files never get here.
    """

    def __init__(self, get_response):
        """Called once at server start; get_response is the rest of the chain and the view."""
        self.get_response = get_response

    def __call__(self, request):
        """Called for every request: pass it on, then log the answer."""
        start = time.monotonic()
        response = self.get_response(request)
        # Render's health check opens the page every 5 seconds: answer it, do not log it (D4).
        if request.headers.get("User-Agent", "").startswith("Render/"):
            return response
        ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "%s %s %s %sms",
            request.method,
            self.safe_path(request),
            response.status_code,
            ms,
        )
        return response

    @staticmethod
    def safe_path(request):
        """The path without the query string; a secret URL as its pattern (R3, R4)."""
        # Matched here, not taken from request.resolver_match: Django sets that only when
        # the request reaches the view, and a middleware may answer first (a user without
        # a role is redirected by OnboardingMiddleware, #10).
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return request.path  # no such URL: nothing to hide
        if match.url_name in SECRET_URL_NAMES:
            return "/" + match.route  # "/accounts/reset/<uidb64>/<token>/"
        return request.path

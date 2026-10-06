"""Onboarding middleware: a user without a role must choose one before anything else (#10)."""

from django.shortcuts import redirect
from django.urls import reverse


class OnboardingMiddleware:
    """Send logged-in users without a role to the role choice, from every page.

    Deny by default: pages added later are covered without extra code (spec decision D1).
    Guests, admins (staff have no role) and users with a role pass through unchanged.
    """

    def __init__(self, get_response):
        """Called once at server start; get_response is the rest of the chain and the view."""
        self.get_response = get_response

    def __call__(self, request):
        """Called for every request: redirect, or pass the request on."""
        user = request.user
        if (
            user.is_authenticated
            and not user.is_staff
            and not user.role
            and not self.is_allowed(request.path)
        ):
            return redirect("role_select")
        return self.get_response(request)

    @staticmethod
    def is_allowed(path):
        """Pages open without a role: the role choice itself, logout and the admin."""
        # Without role_select here the role page would redirect to itself forever.
        open_pages = (reverse("role_select"), reverse("logout"))
        return path in open_pages or path.startswith(reverse("admin:index"))

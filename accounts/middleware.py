"""Our middlewares: onboarding (#10) and the profile language (#29)."""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import translation


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
        """Pages open without a role: the role choice, logout, the language and the admin."""
        # Without role_select here the role page would redirect to itself forever.
        # set_language: the role page has the switcher too (#29, i18n.md R5).
        open_pages = (
            reverse("role_select"),
            reverse("logout"),
            reverse("set_language"),
        )
        return path in open_pages or path.startswith(reverse("admin:index"))


class UserLanguageMiddleware:
    """For a logged-in user, show the site in the language from the profile (#29).

    LocaleMiddleware has already chosen a language from the cookie or the browser; this
    replaces it with `preferred_language`, so the site and the emails (#27) use the same
    language on every device (i18n.md D3). Guests keep LocaleMiddleware's choice.
    """

    def __init__(self, get_response):
        """Called once at server start; get_response is the rest of the chain and the view."""
        self.get_response = get_response

    def __call__(self, request):
        """Called for every request: switch to the profile language, then go on."""
        if request.user.is_authenticated:
            translation.activate(request.user.preferred_language)
            # Templates and Django's own code read the language from here too.
            request.LANGUAGE_CODE = translation.get_language()
        return self.get_response(request)

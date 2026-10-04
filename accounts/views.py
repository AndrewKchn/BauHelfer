"""Views for account pages. Login, logout and password reset use Django's built-in views."""

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView

from .forms import SignupForm


class RegisterView(CreateView):
    """Show the signup form; on success create the user and log them in right away."""

    form_class = SignupForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("home")  # becomes the onboarding page in #10

    def dispatch(self, request, *args, **kwargs):
        """A logged-in user has an account already: send them to the home page."""
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Save the new user, start their session and show a welcome message."""
        response = super().form_valid(form)  # saves the user into self.object
        login(self.request, self.object)
        messages.success(
            self.request, _("Welcome to BauHelfer! Your account is ready.")
        )
        return response

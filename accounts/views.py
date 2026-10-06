"""Views for account pages. Login, logout and password reset use Django's built-in views."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, TemplateView, UpdateView

from .forms import RoleForm, SignupForm


class RegisterView(CreateView):
    """Show the signup form; on success create the user and log them in right away."""

    form_class = SignupForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("role_select")  # onboarding: choose a role first (#10)

    def dispatch(self, request, *args, **kwargs):
        """A logged-in user has an account already: send them to the home page."""
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Save the new user, start their session and show a welcome message."""
        response = super().form_valid(form)  # saves the user into self.object
        login(self.request, self.object)
        messages.success(
            self.request, _("Welcome to BauHelfer! Your account is ready.")
        )
        return response


class RoleSelectView(LoginRequiredMixin, UpdateView):
    """Onboarding: choose "I need workers" or "I am looking for work", once (#10).

    OnboardingMiddleware sends every user without a role here.
    """

    form_class = RoleForm
    template_name = "accounts/role_select.html"

    def dispatch(self, request, *args, **kwargs):
        """The role is chosen once: with a role, GET and POST both go to the profile."""
        if request.user.is_authenticated and request.user.role:
            return redirect(request.user.get_profile_url())
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """The form always edits the logged-in user, never a user from the URL."""
        return self.request.user

    def get_success_url(self):
        """After choosing, go on to the profile form of the new role."""
        return self.object.get_profile_url()


class ProfilePlaceholderView(LoginRequiredMixin, TemplateView):
    """Stands in for the profile forms until #11 (worker) and #12 (employer) replace it."""

    template_name = "accounts/profile_placeholder.html"

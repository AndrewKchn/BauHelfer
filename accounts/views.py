"""Views for account pages. Login, logout and password reset use Django's built-in views."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, TemplateView, UpdateView, View

from .forms import NameAndPhoneForm, RoleForm, SignupForm, WorkerProfileForm
from .models import User


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


class WorkerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Worker pages only: guests go to login, other logged-in users get 403 (spec D7)."""

    def test_func(self):
        """Runs after the login check, so request.user is a real user here."""
        return self.request.user.role == User.Role.WORKER


class WorkerProfileView(WorkerRequiredMixin, TemplateView):
    """The worker's own profile, read-only, with an "Edit" button (#11).

    Always the logged-in worker's profile: there is no id in the URL to change.
    """

    template_name = "accounts/worker_profile.html"

    def get(self, request, *args, **kwargs):
        """No profile yet: there is nothing to show, so go straight to the form."""
        if not hasattr(request.user, "worker_profile"):
            return redirect("worker_profile_edit")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Give the template the profile as `profile`."""
        context = super().get_context_data(**kwargs)
        context["profile"] = self.request.user.worker_profile
        return context


class WorkerProfileEditView(WorkerRequiredMixin, View):
    """Create or edit the worker profile: two forms in one <form> (#11).

    NameAndPhoneForm changes the User, WorkerProfileForm the WorkerProfile.
    """

    template_name = "accounts/worker_profile_form.html"

    def get_forms(self, data=None):
        """Both forms for the logged-in user; without data they show the saved values."""
        user = self.request.user
        profile = getattr(user, "worker_profile", None)  # None until the first save
        return (
            NameAndPhoneForm(data, instance=user),
            WorkerProfileForm(data, instance=profile),
        )

    def get(self, request):
        """Show the forms."""
        user_form, profile_form = self.get_forms()
        return self.show(user_form, profile_form)

    def post(self, request):
        """Save both forms if both are valid; otherwise show them again with errors."""
        user_form, profile_form = self.get_forms(request.POST)
        # A list, not "and": both forms are checked, so all errors show at once.
        if all([user_form.is_valid(), profile_form.is_valid()]):
            with transaction.atomic():  # both saves, or none
                user_form.save()
                profile = profile_form.save(commit=False)
                profile.user = request.user
                profile.save()
            messages.success(request, _("Profile saved."))
            return redirect("worker_profile")
        return self.show(user_form, profile_form)

    def show(self, user_form, profile_form):
        """Render the page with both forms."""
        return render(
            self.request,
            self.template_name,
            {"user_form": user_form, "profile_form": profile_form},
        )


class ProfilePlaceholderView(LoginRequiredMixin, TemplateView):
    """Stands in for the employer profile form until #12 replaces it."""

    template_name = "accounts/profile_placeholder.html"

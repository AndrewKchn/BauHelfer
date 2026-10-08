"""Views for account pages. Login, logout and password reset use Django's built-in views."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, TemplateView, UpdateView, View

from .forms import (
    EmployerProfileForm,
    NameAndPhoneForm,
    RoleForm,
    SignupForm,
    WorkerProfileForm,
    WorkerUserForm,
)
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


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Pages of one role: guests go to login, other logged-in users get 403 (#11 spec D7).

    Subclasses set `role`.
    """

    role = None

    def test_func(self):
        """Runs after the login check, so request.user is a real user here."""
        return self.request.user.role == self.role


class ProfileView(RoleRequiredMixin, TemplateView):
    """The user's own profile, read-only, with an "Edit" button.

    Always the logged-in user's profile: there is no id in the URL to change.
    Subclasses set `role`, `template_name`, `profile_name` (the related_name on User)
    and `edit_url_name`.
    """

    profile_name = None
    edit_url_name = None

    def get(self, request, *args, **kwargs):
        """No profile yet: there is nothing to show, so go straight to the form."""
        if not hasattr(request.user, self.profile_name):
            return redirect(self.edit_url_name)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Give the template the profile as `profile`."""
        context = super().get_context_data(**kwargs)
        context["profile"] = getattr(self.request.user, self.profile_name)
        return context


class ProfileEditView(RoleRequiredMixin, View):
    """Create or edit the user's own profile: two forms in one <form>.

    `user_form_class` changes the User, `profile_form_class` the profile.
    Subclasses set `role`, `template_name`, `profile_form_class`, `profile_name`
    and `success_url_name`, and may change `user_form_class`.
    """

    template_name = None
    user_form_class = NameAndPhoneForm
    profile_form_class = None
    profile_name = None
    success_url_name = None

    def get_forms(self, data=None):
        """Both forms for the logged-in user; without data they show the saved values."""
        user = self.request.user
        profile = getattr(user, self.profile_name, None)  # None until the first save
        return (
            self.user_form_class(data, instance=user),
            self.profile_form_class(data, instance=profile),
        )

    def get(self, request):
        """Show the forms."""
        user_form, profile_form = self.get_forms()
        return self.show(user_form, profile_form)

    def post(self, request):
        """Save both forms if both are valid; otherwise show them again with errors."""
        user_form, profile_form = self.get_forms(request.POST)
        # A list, not "and": both forms are validated here, in one place. (With "and" the
        # second form would still show its errors: form.errors validates on first use.)
        if all([user_form.is_valid(), profile_form.is_valid()]):
            with transaction.atomic():  # both saves, or none
                user_form.save()
                profile = profile_form.save(commit=False)
                profile.user = request.user
                profile.save()
            messages.success(request, _("Profile saved."))
            return redirect(self.success_url_name)
        return self.show(user_form, profile_form)

    def show(self, user_form, profile_form):
        """Render the page with both forms."""
        return render(
            self.request,
            self.template_name,
            {"user_form": user_form, "profile_form": profile_form},
        )


class WorkerProfileView(ProfileView):
    """The worker's own profile page (#11)."""

    role = User.Role.WORKER
    template_name = "accounts/worker_profile.html"
    profile_name = "worker_profile"
    edit_url_name = "worker_profile_edit"


class WorkerProfileEditView(ProfileEditView):
    """Create or edit the worker profile: team size, skills, languages, status (#11)."""

    role = User.Role.WORKER
    template_name = "accounts/worker_profile_form.html"
    user_form_class = WorkerUserForm  # adds the work-permit checkbox (#13)
    profile_form_class = WorkerProfileForm
    profile_name = "worker_profile"
    success_url_name = "worker_profile"


class EmployerProfileView(ProfileView):
    """The employer's own profile page (#12)."""

    role = User.Role.EMPLOYER
    template_name = "accounts/employer_profile.html"
    profile_name = "employer_profile"
    edit_url_name = "employer_profile_edit"


class EmployerProfileEditView(ProfileEditView):
    """Create or edit the employer profile: company name and trades (#12)."""

    role = User.Role.EMPLOYER
    template_name = "accounts/employer_profile_form.html"
    profile_form_class = EmployerProfileForm
    profile_name = "employer_profile"
    success_url_name = "employer_profile"

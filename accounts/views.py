"""Views for account pages. Login extends Django's view; logout and password reset use it as is."""

import logging
from typing import override

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    TemplateView,
    UpdateView,
    View,
)

from .emails import send_verification_email
from .forms import (
    EmployerProfileForm,
    NameAndPhoneForm,
    ResendVerificationForm,
    RoleForm,
    SignupForm,
    WorkerProfileForm,
    WorkerUserForm,
)
from .models import SiteSettings, User
from .tokens import email_verification_token

# "accounts.views". Ids only, never an email or other personal data (#124).
logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    """Django's login, but an employer lands on "My jobs" (#20, docs/specs/my-jobs.md D4).

    Django asks get_default_redirect_url() only when there is no safe `?next=` address, so
    a `?next=` still wins. After a successful login request.user is the new user.
    """

    @override
    def get_default_redirect_url(self):
        """ "My jobs" for an employer; LOGIN_REDIRECT_URL (the home page) for everyone else."""
        if self.request.user.role == User.Role.EMPLOYER:
            return reverse("my_jobs")
        return super().get_default_redirect_url()


class RegisterView(CreateView):
    """Show the signup form; on success save an inactive user and email them the link (#81).

    docs/specs/email-verification.md R1. The account works after the link is opened
    (VerifyEmailView).
    """

    form_class = SignupForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("register_done")

    @override
    def dispatch(self, request, *args, **kwargs):
        """A logged-in user has an account already: send them to the home page."""
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    @override
    def form_valid(self, form):
        """Save the new user inactive, send the link, remember the address for the next page.

        With the demo switch off (R14) the user is active and logged in at once, as before
        #81, and gets no email.
        """
        required = (
            SiteSettings.load().email_verification_required
        )  # read each time (D13)
        form.instance.is_active = not required  # inactive until the link is opened (R1)
        response = super().form_valid(form)  # saves the user into self.object
        logger.info("User registered: user_id=%s", self.object.pk)
        if not required:
            login(self.request, self.object)
            messages.success(
                self.request, _("Welcome to BauHelfer! Your account is ready.")
            )
            return redirect("role_select")  # onboarding: choose a role first (#10)
        send_verification_email(self.request, self.object)
        # For "We sent a link to …" on the next page (R2, D7); the session is per browser.
        self.request.session["signup_email"] = self.object.email
        return response


class RegisterDoneView(TemplateView):
    """ "Check your email": names the address the link went to (#81, R2)."""

    template_name = "registration/register_done.html"

    @override
    def get_context_data(self, **kwargs):
        """The address from the signup in this browser; None if the page is opened alone."""
        context = super().get_context_data(**kwargs)
        context["email"] = self.request.session.get("signup_email")
        return context


class VerifyEmailView(View):
    """The link from the email: GET shows a button, POST confirms and logs in (#81, R5).

    The link holds the user id (base64) and the token; GET changes nothing, as mail
    scanners open links too (D6).
    """

    template_name = "registration/verify_email.html"

    def get_user(self, uidb64, token):
        """The user the link was made for, or None for a wrong, used or expired link."""
        try:
            user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode())
        # Not base64, not a number, no such user: all mean a made-up link.
        except (
            ValueError,
            TypeError,
            OverflowError,
            ValidationError,
            User.DoesNotExist,
        ):
            return None
        if not email_verification_token.check_token(user, token):
            return None
        return user

    def get(self, request, uidb64, token):
        """Show the "Confirm email" button, or the "link is not valid" text."""
        user = self.get_user(uidb64, token)
        return render(request, self.template_name, {"validlink": user is not None})

    def post(self, request, uidb64, token):
        """Confirm the address, activate the account, log in, go to the role choice."""
        user = self.get_user(uidb64, token)
        if user is None:
            return render(request, self.template_name, {"validlink": False})
        user.is_active = True
        user.email_verified_at = timezone.now()  # also uses the link up (tokens.py)
        user.save(update_fields=["is_active", "email_verified_at"])
        login(request, user)
        logger.info("Email confirmed: user_id=%s", user.pk)
        messages.success(request, _("Your email is confirmed. Welcome to BauHelfer!"))
        return redirect("role_select")  # onboarding: choose a role first (#10)


class ResendVerificationView(FormView):
    """ "Send the link again": the same answer for every address (#81, R8, R9).

    As password reset: the next page never tells whether an email went out, so the form
    does not show which addresses are registered, confirmed or in the 10-minute pause.
    """

    form_class = ResendVerificationForm
    template_name = "registration/verify_email_resend.html"
    success_url = reverse_lazy("verify_email_resend_done")

    @override
    def form_valid(self, form):
        """Send a new link if the account may get one (R9); go on to the same page anyway."""
        try:
            user = User.objects.get_by_natural_key(form.cleaned_data["email"])
        except User.DoesNotExist:
            pass
        else:
            if user.can_get_verification_email():
                send_verification_email(self.request, user)
        return super().form_valid(form)


class RoleSelectView(LoginRequiredMixin, UpdateView):
    """Onboarding: choose "I need workers" or "I am looking for work", once (#10).

    OnboardingMiddleware sends every user without a role here.
    """

    form_class = RoleForm
    template_name = "accounts/role_select.html"

    @override
    def dispatch(self, request, *args, **kwargs):
        """The role is chosen once: with a role, GET and POST both go to the profile."""
        if request.user.is_authenticated and request.user.role:
            return redirect(request.user.get_profile_url())
        return super().dispatch(request, *args, **kwargs)

    @override
    def get_object(self, queryset=None):
        """The form always edits the logged-in user, never a user from the URL."""
        return self.request.user

    @override
    def get_success_url(self):
        """After choosing, go on to the profile form of the new role."""
        return self.object.get_profile_url()


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Pages of one role: guests go to login, other logged-in users get 403 (#11 spec D7).

    Subclasses set `role`.
    """

    role = None

    @override
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

    @override
    def get(self, request, *args, **kwargs):
        """No profile yet: there is nothing to show, so go straight to the form."""
        if not hasattr(request.user, self.profile_name):
            return redirect(self.edit_url_name)
        return super().get(request, *args, **kwargs)

    @override
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


class WorkerDetailView(RoleRequiredMixin, DetailView):
    """A worker's profile as an employer sees it, without contacts (#23).

    docs/specs/applications-list.md R7, D2, D4, D10. Employers only: guests go to login,
    workers get 403, also for their own id (their page is worker_profile).
    """

    role = User.Role.EMPLOYER
    template_name = "accounts/worker_detail.html"
    context_object_name = "worker"

    @override
    def get_queryset(self):
        """Only workers who applied to one of the logged-in employer's jobs (D2).

        get_object() looks the id from the URL up in here, so anyone else, an employer's id
        or an unknown id gives 404 (D4). distinct(): a worker who applied to two of the
        employer's jobs would be found twice, and get_object() would fail.
        """
        return (
            User.objects.filter(
                worker_profile__isnull=False,
                applications__job__employer=self.request.user,
            )
            .select_related("worker_profile")
            .distinct()
        )

    @override
    def get_context_data(self, **kwargs):
        """Give the shared profile card its `profile`."""
        context = super().get_context_data(**kwargs)
        context["profile"] = self.object.worker_profile
        return context


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

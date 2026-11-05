"""URLs of the account pages, mounted under /accounts/.

No app namespace: Django's built-in auth views look these names up as plain "login",
"password_reset_done" and so on.
"""

from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

from . import views
from .forms import ConfirmedPasswordResetForm, LoginForm

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("register/done/", views.RegisterDoneView.as_view(), name="register_done"),
    # Before the link below: "verify/resend/done/" would match it too (#81).
    path(
        "verify/resend/",
        views.ResendVerificationView.as_view(),
        name="verify_email_resend",
    ),
    path(
        "verify/resend/done/",
        TemplateView.as_view(
            template_name="registration/verify_email_resend_done.html"
        ),
        name="verify_email_resend_done",
    ),
    # The link from the confirmation email (#81): the user id in base64 and the token.
    path(
        "verify/<uidb64>/<token>/",
        views.VerifyEmailView.as_view(),
        name="verify_email",
    ),
    path(
        "login/",
        # Django's LoginView with the landing page by role (#20).
        views.LoginView.as_view(
            authentication_form=LoginForm, redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only
    path("onboarding/", views.RoleSelectView.as_view(), name="role_select"),
    path("profile/worker/", views.WorkerProfileView.as_view(), name="worker_profile"),
    path(
        "profile/worker/edit/",
        views.WorkerProfileEditView.as_view(),
        name="worker_profile_edit",
    ),
    # Another worker's profile, for the employers they applied to (#23): pk = the user id.
    path("workers/<int:pk>/", views.WorkerDetailView.as_view(), name="worker_detail"),
    path(
        "profile/employer/",
        views.EmployerProfileView.as_view(),
        name="employer_profile",
    ),
    path(
        "profile/employer/edit/",
        views.EmployerProfileEditView.as_view(),
        name="employer_profile_edit",
    ),
    # Password reset in four steps: ask for the email -> "email sent" -> new password -> done.
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            # Only to confirmed addresses (#27, docs/specs/notifications.md D13).
            form_class=ConfirmedPasswordResetForm,
            # .txt, not .html: an email is not a page and does not extend base.html.
            email_template_name="registration/password_reset_email.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]

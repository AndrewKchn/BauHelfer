"""URLs of the account pages, mounted under /accounts/.

No app namespace: Django's built-in auth views look these names up as plain "login",
"password_reset_done" and so on.
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=LoginForm, redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only
    path("onboarding/", views.RoleSelectView.as_view(), name="role_select"),
    # Placeholders: #11 and #12 put the real profile forms under these names.
    path(
        "profile/worker/",
        views.ProfilePlaceholderView.as_view(),
        name="worker_profile_edit",
    ),
    path(
        "profile/employer/",
        views.ProfilePlaceholderView.as_view(),
        name="employer_profile_edit",
    ),
    # Password reset in four steps: ask for the email -> "email sent" -> new password -> done.
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
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

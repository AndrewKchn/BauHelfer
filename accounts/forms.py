"""Forms for signing up, logging in and for the user admin pages."""

from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.utils.translation import gettext_lazy as _

from .models import User


# Django's admin forms are tied to the default User with a username field;
# these point them at our model and its email login.
class UserAdminCreationForm(AdminUserCreationForm):
    """The admin "Add user" form: email and password instead of username."""

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email",)


class UserAdminChangeForm(UserChangeForm):
    """The admin form for editing an existing user."""

    class Meta(UserChangeForm.Meta):
        model = User


class SignupForm(UserCreationForm):
    """The public registration form: email and the password twice.

    UserCreationForm checks that both passwords match, runs the password validators from
    settings and saves the password as a hash. Role, name and phone come later (#10-#12).
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)


class LoginForm(AuthenticationForm):
    """Django's login form with an error text that fits email login.

    The default text says "both fields may be case-sensitive", but our email is not:
    UserManager.get_by_natural_key finds the user in any capitalisation.
    """

    def __init__(self, *args, **kwargs):
        """Replace only the "wrong email or password" text, keep Django's other errors."""
        super().__init__(*args, **kwargs)
        self.error_messages = {
            **self.error_messages,
            "invalid_login": _("Wrong email or password."),
        }

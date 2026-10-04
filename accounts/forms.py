"""Forms for signing up and for the user admin pages."""

from django.contrib.auth.forms import (
    AdminUserCreationForm,
    UserChangeForm,
    UserCreationForm,
)

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

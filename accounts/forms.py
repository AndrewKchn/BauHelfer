"""Forms for the user admin pages."""

from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

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

"""Forms for signing up, logging in, choosing a role, the profiles and the user admin."""

from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import EmployerProfile, Skill, SpokenLanguage, Trade, User, WorkerProfile


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


class RoleForm(forms.ModelForm):
    """Onboarding: the user picks "employer" or "worker" (#10).

    Only the role field is listed, so other fields sent with the form (like is_staff)
    are ignored. Django checks the value against User.Role, so "admin" is rejected.
    """

    class Meta:
        model = User
        fields = ("role",)

    def __init__(self, *args, **kwargs):
        """Make the role required: the model allows an empty role only for admins."""
        super().__init__(*args, **kwargs)
        self.fields["role"].required = True


class NameAndPhoneForm(forms.ModelForm):
    """The user's own name and phone, shown on the profile forms (#11).

    These live on User, not on the profile, so the profile page uses two forms at once.
    """

    class Meta:
        model = User
        fields = ("name", "phone")

    def __init__(self, *args, **kwargs):
        """Make the name required: employers need to know who applied (spec D5)."""
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True


class WorkerUserForm(NameAndPhoneForm):
    """Name and phone plus the work-permit checkbox, for workers only (#13, spec D4).

    The box is required, so a worker profile cannot be saved without it. The model stores a
    date, not a yes/no: save() fills it in the first time (spec D2, D5).
    """

    work_permit = forms.BooleanField(
        label=_("I am allowed to work in Germany"),
        help_text=_(
            "For example as an EU citizen, or with a residence permit that allows work."
        ),
        widget=forms.CheckboxInput(attrs={"class": "checkbox"}),
    )

    def __init__(self, *args, **kwargs):
        """Tick the box for a worker who has already confirmed."""
        super().__init__(*args, **kwargs)
        self.fields["work_permit"].initial = (
            self.instance.work_permit_confirmed_at is not None
        )

    def save(self, commit=True):
        """Save name and phone; store the date of the first confirmation only."""
        user = super().save(commit=False)
        if user.work_permit_confirmed_at is None:
            user.work_permit_confirmed_at = timezone.now()
        if commit:
            user.save()
        return user


class WorkerProfileForm(forms.ModelForm):
    """The worker profile: team size, skills, languages and legal status (#11).

    No user field: the view always saves the profile for the logged-in user.
    """

    # An ArrayField gets a comma-separated text box by default; checkboxes are easier.
    skills = forms.MultipleChoiceField(
        label=_("Skills"),
        choices=Skill.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox"}),
    )
    languages = forms.MultipleChoiceField(
        label=_("Languages you speak"),
        choices=SpokenLanguage.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox"}),
    )
    # Declared here, so the radio buttons have no empty "---------" choice.
    legal_status = forms.ChoiceField(
        label=_("Legal status"),
        choices=WorkerProfile.LegalStatus.choices,
        widget=forms.RadioSelect(attrs={"class": "radio"}),
    )

    class Meta:
        model = WorkerProfile
        fields = ("team_size", "skills", "languages", "legal_status")

    def __init__(self, *args, **kwargs):
        """Let the browser's number field allow only 1-10, like the model."""
        super().__init__(*args, **kwargs)
        self.fields["team_size"].widget.attrs.update(min=1, max=10)


class EmployerProfileForm(forms.ModelForm):
    """The employer profile: company name and trades (#12).

    No user field: the view always saves the profile for the logged-in user.
    """

    # Checkboxes instead of the ArrayField's comma-separated text box, as for skills.
    trades = forms.MultipleChoiceField(
        label=_("Trades"),
        choices=Trade.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox"}),
    )

    class Meta:
        model = EmployerProfile
        fields = ("company_name", "trades")

"""User accounts: one User model for employers and workers, with email login."""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Creates users with email as the login instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Save a user with a normalized email and a hashed password."""
        if not email:
            raise ValueError("The email must be set.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)  # stores a hash, never the plain password
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create a normal user (employer or worker), without admin rights."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create an admin who can log in to /admin/ and has all permissions."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    @classmethod
    def normalize_email(cls, email):
        """Lowercase the whole address, not only the domain: Anna@ and anna@ are one person."""
        return (email or "").strip().lower()

    def get_by_natural_key(self, email):
        """Find the user for authenticate(): log in with any capitalisation of the email."""
        return self.get(email__iexact=email)


class User(AbstractUser):
    """A BauHelfer account: an employer or a worker (or crew), logging in with email."""

    class Role(models.TextChoices):
        EMPLOYER = "employer", _("Employer")
        WORKER = "worker", _("Worker")

    class Language(models.TextChoices):
        GERMAN = "de", "Deutsch"
        ENGLISH = "en", "English"
        RUSSIAN = "ru", "Русский"
        UKRAINIAN = "uk", "Українська"
        POLISH = "pl", "Polski"
        ROMANIAN = "ro", "Română"
        TURKISH = "tr", "Türkçe"

    # Replace AbstractUser's username and first/last name with email and one name field.
    username = None
    first_name = None
    last_name = None

    email = models.EmailField(_("email"), unique=True)
    name = models.CharField(_("name"), max_length=150, blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    # Empty until the user picks a role in onboarding (#10); admins have none.
    role = models.CharField(_("role"), max_length=10, choices=Role.choices, blank=True)
    preferred_language = models.CharField(
        _("preferred language"),
        max_length=2,
        choices=Language.choices,
        default=Language.ENGLISH,
    )
    work_permit_confirmed = models.BooleanField(
        _("allowed to work in Germany"), default=False
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ()  # asked by createsuperuser besides email and password

    objects = UserManager()

    def __str__(self):
        return self.email

    def get_profile_url(self):
        """The profile form for this user's role; the role choice while there is no role."""
        url_names = {
            self.Role.WORKER: "worker_profile_edit",
            self.Role.EMPLOYER: "employer_profile_edit",
        }
        return reverse(url_names.get(self.role, "role_select"))

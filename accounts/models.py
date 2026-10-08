"""User accounts: one User model for employers and workers, with email login."""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .validators import validate_phone


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
    phone = models.CharField(
        _("phone"),
        max_length=30,
        blank=True,
        validators=[validate_phone],
        help_text=_("For example +49 151 12345678 or 0151 12345678."),
    )
    # Empty until the user picks a role in onboarding (#10); admins have none.
    role = models.CharField(_("role"), max_length=10, choices=Role.choices, blank=True)
    preferred_language = models.CharField(
        _("preferred language"),
        max_length=2,
        choices=Language.choices,
        default=Language.ENGLISH,
    )
    # When the worker ticked "I am allowed to work in Germany" (#13); empty = not yet.
    # Their own statement, not a document check (docs/specs/work-permit.md).
    work_permit_confirmed_at = models.DateTimeField(
        _("work permit confirmed at"), null=True, blank=True
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ()  # asked by createsuperuser besides email and password

    objects = UserManager()

    def __str__(self):
        return self.email

    def can_apply(self):
        """Whether this user may apply to jobs (#22): a worker with profile and work permit."""
        return (
            self.role == self.Role.WORKER
            and hasattr(self, "worker_profile")  # False while there is no profile
            and self.work_permit_confirmed_at is not None
        )

    def get_profile_url(self):
        """The profile form for this user's role; the role choice while there is no role."""
        url_names = {
            self.Role.WORKER: "worker_profile_edit",
            self.Role.EMPLOYER: "employer_profile_edit",
        }
        return reverse(url_names.get(self.role, "role_select"))


class Skill(models.TextChoices):
    """Helper jobs a worker can do (#11). A fixed list, so .po files translate the names."""

    DEMOLITION = "demolition", _("Demolition")
    DEBRIS_CLEARING = "debris_clearing", _("Debris clearing")
    CARRYING = "carrying", _("Carrying materials")
    EARTHWORKS = "earthworks", _("Earthworks / digging")
    SITE_CLEANING = "site_cleaning", _("Site cleaning")
    SCAFFOLDING = "scaffolding", _("Scaffolding helper")
    MASONRY = "masonry", _("Bricklayer's helper")
    DRYWALL = "drywall", _("Drywall helper")
    PLASTERING = "plastering", _("Plastering helper")
    PAINTING = "painting", _("Painting helper")


class SpokenLanguage(models.TextChoices):
    """Languages a worker speaks; not the site language (User.preferred_language)."""

    GERMAN = "de", _("German")
    ENGLISH = "en", _("English")
    RUSSIAN = "ru", _("Russian")
    UKRAINIAN = "uk", _("Ukrainian")
    POLISH = "pl", _("Polish")
    ROMANIAN = "ro", _("Romanian")
    TURKISH = "tr", _("Turkish")
    BULGARIAN = "bg", _("Bulgarian")
    CROATIAN = "hr", _("Croatian")
    SERBIAN = "sr", _("Serbian")
    BOSNIAN = "bs", _("Bosnian")
    HUNGARIAN = "hu", _("Hungarian")
    ALBANIAN = "sq", _("Albanian")
    ARABIC = "ar", _("Arabic")
    ITALIAN = "it", _("Italian")


class WorkerProfile(models.Model):
    """What a worker or a small crew offers (#11). One per worker, filled in to apply."""

    class LegalStatus(models.TextChoices):
        GEWERBE = "gewerbe", _("Self-employed (Gewerbe)")
        MINIJOB = "minijob", _("Minijob")
        EMPLOYED = "employed", _("Employed")

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,  # deleting the account deletes the profile
        related_name="worker_profile",
        verbose_name=_("user"),
    )
    # The validators check forms; the constraint in Meta checks the database itself.
    team_size = models.PositiveSmallIntegerField(
        _("team size"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_("1 = only you. 2-10 = your crew, including you."),
    )
    # A PostgreSQL array of codes, e.g. {demolition,carrying}: no extra table needed.
    skills = ArrayField(
        models.CharField(max_length=20, choices=Skill.choices),
        verbose_name=_("skills"),
    )
    languages = ArrayField(
        models.CharField(max_length=2, choices=SpokenLanguage.choices),
        verbose_name=_("spoken languages"),
    )
    legal_status = models.CharField(
        _("legal status"), max_length=10, choices=LegalStatus.choices
    )

    class Meta:
        verbose_name = _("worker profile")
        verbose_name_plural = _("worker profiles")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(team_size__gte=1, team_size__lte=10),
                name="worker_team_size_1_to_10",
            ),
        )

    def __str__(self):
        return str(self.user)

    def team_label(self):
        """Team size in words: "Individual" or "Crew of 3"."""
        if self.team_size == 1:
            return _("Individual")
        # ngettext: some languages (Russian, Polish, ...) need other forms for 2-4 and 5+.
        return ngettext("Crew of %(count)d", "Crew of %(count)d", self.team_size) % {
            "count": self.team_size
        }

    def skill_names(self):
        """The chosen skills as names in the user's language, in the chosen order."""
        return [str(Skill(code).label) for code in self.skills]

    def language_names(self):
        """The spoken languages as names in the user's language, in the chosen order."""
        return [str(SpokenLanguage(code).label) for code in self.languages]


class Trade(models.TextChoices):
    """What an employer does (#12). A fixed list, so .po files translate the names."""

    WINDOW_FITTING = "window_fitting", _("Window fitting")
    DRYWALL = "drywall", _("Drywall")
    PLASTERING = "plastering", _("Plastering")
    PAINTING = "painting", _("Painting")
    TILING = "tiling", _("Tiling")
    ROOFING = "roofing", _("Roofing")
    BRICKLAYING = "bricklaying", _("Bricklaying")
    CARPENTRY = "carpentry", _("Carpentry")
    ELECTRICAL = "electrical", _("Electrical")
    PLUMBING_HEATING = "plumbing_heating", _("Plumbing & heating")
    LANDSCAPING = "landscaping", _("Landscaping")
    DEMOLITION = "demolition", _("Demolition")
    GENERAL_CONTRACTOR = "general_contractor", _("General contractor")
    PRIVATE_PERSON = "private_person", _("Private person")
    OTHER = "other", _("Other")


class EmployerProfile(models.Model):
    """Who posts the jobs: a company or a private person (#12). One per employer."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,  # deleting the account deletes the profile
        related_name="employer_profile",
        verbose_name=_("user"),
    )
    # Optional: a private person renovating a flat has no company (spec D2).
    company_name = models.CharField(
        _("company name"),
        max_length=150,
        blank=True,
        help_text=_("Leave empty if you hire as a private person."),
    )
    # Several trades, e.g. {drywall,painting}, stored like WorkerProfile.skills (spec D1).
    trades = ArrayField(
        models.CharField(max_length=20, choices=Trade.choices),
        verbose_name=_("trades"),
    )

    class Meta:
        verbose_name = _("employer profile")
        verbose_name_plural = _("employer profiles")

    def __str__(self):
        return str(self.user)

    def display_name(self):
        """The company name, or the person's name when there is no company."""
        return self.company_name or self.user.name

    def trade_names(self):
        """The trades as names in the user's language, in the chosen order."""
        return [str(Trade(code).label) for code in self.trades]

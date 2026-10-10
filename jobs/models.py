"""Jobs: what an employer posts and workers apply to (#15)."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import Skill, User

# German minimum wage per hour from 1 January 2026. Only a validator uses it, not a database
# constraint: when it rises, old jobs at the old rate must still be valid (docs/specs/job.md D5).
MINIMUM_WAGE = Decimal("13.90")


class District(models.TextChoices):
    """The 25 Munich Stadtbezirke in official order, plus one entry outside the city (#11)."""

    # District names are proper names: the same in every language, so not translated.
    ALTSTADT_LEHEL = "altstadt_lehel", "Altstadt-Lehel"
    LUDWIGSVORSTADT_ISARVORSTADT = (
        "ludwigsvorstadt_isarvorstadt",
        "Ludwigsvorstadt-Isarvorstadt",
    )
    MAXVORSTADT = "maxvorstadt", "Maxvorstadt"
    SCHWABING_WEST = "schwabing_west", "Schwabing-West"
    AU_HAIDHAUSEN = "au_haidhausen", "Au-Haidhausen"
    SENDLING = "sendling", "Sendling"
    SENDLING_WESTPARK = "sendling_westpark", "Sendling-Westpark"
    SCHWANTHALERHOEHE = "schwanthalerhoehe", "Schwanthalerhöhe"
    NEUHAUSEN_NYMPHENBURG = "neuhausen_nymphenburg", "Neuhausen-Nymphenburg"
    MOOSACH = "moosach", "Moosach"
    MILBERTSHOFEN_AM_HART = "milbertshofen_am_hart", "Milbertshofen-Am Hart"
    SCHWABING_FREIMANN = "schwabing_freimann", "Schwabing-Freimann"
    BOGENHAUSEN = "bogenhausen", "Bogenhausen"
    BERG_AM_LAIM = "berg_am_laim", "Berg am Laim"
    TRUDERING_RIEM = "trudering_riem", "Trudering-Riem"
    RAMERSDORF_PERLACH = "ramersdorf_perlach", "Ramersdorf-Perlach"
    OBERGIESING_FASANGARTEN = "obergiesing_fasangarten", "Obergiesing-Fasangarten"
    UNTERGIESING_HARLACHING = "untergiesing_harlaching", "Untergiesing-Harlaching"
    THALKIRCHEN_OBERSENDLING_FORSTENRIED_FUERSTENRIED_SOLLN = (
        "thalkirchen_obersendling_forstenried_fuerstenried_solln",
        "Thalkirchen-Obersendling-Forstenried-Fürstenried-Solln",
    )
    HADERN = "hadern", "Hadern"
    PASING_OBERMENZING = "pasing_obermenzing", "Pasing-Obermenzing"
    AUBING_LOCHHAUSEN_LANGWIED = (
        "aubing_lochhausen_langwied",
        "Aubing-Lochhausen-Langwied",
    )
    ALLACH_UNTERMENZING = "allach_untermenzing", "Allach-Untermenzing"
    FELDMOCHING_HASENBERGL = "feldmoching_hasenbergl", "Feldmoching-Hasenbergl"
    LAIM = "laim", "Laim"
    OUTSIDE_MUNICH = "outside_munich", _("Munich area (outside the city)")


class Job(models.Model):
    """One job posting: what work, where, when, for how many people and for how much."""

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        FILLED = "filled", _("Filled")
        DONE = "done", _("Done")
        CANCELLED = "cancelled", _("Cancelled")

    employer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,  # deleting the account deletes its jobs (spec D4)
        related_name="jobs",
        # Forms and the admin offer only employers in the drop-down.
        limit_choices_to={"role": User.Role.EMPLOYER},
        verbose_name=_("employer"),
    )
    # The same list as the worker skills, so jobs can be matched to workers (spec D1).
    job_type = models.CharField(_("job type"), max_length=20, choices=Skill.choices)
    description = models.TextField(_("description"))
    # The language the description is written in; the translation (#38) starts from it.
    original_language = models.CharField(
        _("original language"), max_length=2, choices=User.Language.choices
    )
    address = models.CharField(_("address"), max_length=200)
    district = models.CharField(_("district"), max_length=60, choices=District.choices)
    # 6 decimal places are about 10 cm; empty until geocoding (#41) fills them (spec D3).
    latitude = models.DecimalField(
        _("latitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        _("longitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    date = models.DateField(_("date"))
    start_time = models.TimeField(_("start time"))
    # The validators check forms; the constraints in Meta check the database itself.
    # At most 10 hours: the legal maximum per working day, § 3 ArbZG (spec D8).
    hours = models.PositiveSmallIntegerField(
        _("hours"), validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    workers_needed = models.PositiveSmallIntegerField(
        _("workers needed"), validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    # Decimal, not float: money must not turn 18.10 into 18.0999999.
    hourly_rate = models.DecimalField(
        _("hourly rate (€)"),
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(MINIMUM_WAGE)],
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.OPEN
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("job")
        verbose_name_plural = _("jobs")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(hours__gte=1, hours__lte=10),
                name="job_hours_1_to_10",
            ),
            models.CheckConstraint(
                condition=models.Q(workers_needed__gte=1, workers_needed__lte=10),
                name="job_workers_needed_1_to_10",
            ),
        )

    def __str__(self):
        return f"{self.get_job_type_display()} – {self.date}"

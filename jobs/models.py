"""Jobs: what an employer posts and workers apply to (#15), and their photos (#64)."""

import uuid
from datetime import datetime, timedelta
from typing import override

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Skill, User

from .photos import make_thumbnail

# The lowest minimum wage in settings: the floor for every job, checked by the model
# validator. The form checks the rate of the job's own date (minimum_wage_on, #16).
# Only a validator, not a database constraint: when the wage rises, old jobs at the old
# rate must still be valid (docs/specs/job.md D5).
MINIMUM_WAGE = min(settings.MINIMUM_WAGES.values())


def minimum_wage_on(day):
    """The minimum wage on `day`: the rate with the latest start date on or before it."""
    # Read settings on every call, not once at import: tests and future rates change it.
    wages = settings.MINIMUM_WAGES
    # Latest start date first, so the first one on or before the day is the right one.
    for start_date in sorted(wages, reverse=True):
        if start_date <= day:
            return wages[start_date]
    # A day before the first start date gets the earliest rate.
    return wages[min(wages)]


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


class JobQuerySet(models.QuerySet):
    """Ready-made filters for jobs, used as Job.objects.<name>()."""

    def open(self):
        """Jobs workers can still apply to; the job list (#18) shows only these."""
        return self.filter(status=Job.Status.OPEN)

    def upcoming(self):
        """Jobs that have not started yet; the job list (#18) shows only these."""
        # A job's date and start time are Munich time, so compare them with Munich's "now",
        # not with UTC.
        now = timezone.localtime()
        later_today = models.Q(date=now.date(), start_time__gt=now.time())
        return self.filter(models.Q(date__gt=now.date()) | later_today)


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

    # At most this many photos per job; the forms check it (docs/specs/job-photos.md D6).
    MAX_PHOTOS = 5

    objects = JobQuerySet.as_manager()  # adds Job.objects.open()

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

    @property
    def end_time(self):
        """When the job ends: start time plus hours; past midnight gives the next morning."""
        # A time cannot be added to, a date and time can; only the time is returned.
        start = datetime.combine(self.date, self.start_time)
        end = start + timedelta(hours=self.hours)
        return end.time()


def job_photo_path(instance, filename):
    """Where a photo is stored: a random name, never the original one (job-photos.md D7).

    Django calls this when the file is saved. The original name can hold a person's name,
    and two uploads called photo.jpg must not clash. Always .jpg: prepare_photo() turns every
    photo into a JPEG.
    """
    return f"job_photos/{uuid.uuid4().hex}.jpg"


def job_thumbnail_path(instance, filename):
    """Where a photo's small copy is stored: a random name like the photo (R24, D7)."""
    return f"job_photos/thumbs/{uuid.uuid4().hex}.jpg"


class JobPhoto(models.Model):
    """One photo of a job, already resized and without EXIF (prepare_photo(), #64)."""

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,  # the photos go with their job
        related_name="photos",  # job.photos.all()
        verbose_name=_("job"),
    )
    # The database keeps only the path (job_photos/….jpg); the file is in the storage of
    # settings.STORAGES["default"]: media/ locally, Supabase in production.
    image = models.ImageField(_("photo"), upload_to=job_photo_path)
    # 300 × 300 for the job list (iteration 3). Empty for photos saved before it existed:
    # thumbnail_url then gives the big photo (D29).
    thumbnail = models.ImageField(
        _("thumbnail"), upload_to=job_thumbnail_path, blank=True
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("job photo")
        verbose_name_plural = _("job photos")
        # Oldest first: the first photo is the one the job list shows. The id breaks ties
        # between photos saved in the same instant.
        ordering = ("uploaded_at", "id")

    def __str__(self):
        return self.image.name

    @override
    def save(self, *args, **kwargs):
        """Make the small copy the first time the photo is saved (R26).

        Here, not in the forms: the admin, the edit page and tests all save through this.
        Saving again keeps the copy that is there.
        """
        if self.image and not self.thumbnail:
            self.thumbnail = make_thumbnail(self.image)
        super().save(*args, **kwargs)

    @property
    def thumbnail_url(self):
        """The small copy's address, or the photo's if it has none (R27)."""
        return (self.thumbnail or self.image).url


@receiver(post_delete, sender=JobPhoto)
def delete_photo_file(sender, instance, **kwargs):
    """Delete the photo's files when its row is deleted (job-photos.md R7, R28, D8).

    Django never deletes a file by itself. A signal, not a delete() method: delete() is not
    called when the photo goes with its job or account (cascade) or in a bulk delete, but
    this signal is sent for every row. on_commit: if the transaction is rolled back, the row
    comes back, so the file must still be there.
    """
    # Both files: the photo and its small copy (R28); an old photo may have no copy.
    names = [file.name for file in (instance.image, instance.thumbnail) if file]
    storage = instance.image.storage

    def delete_files():
        for name in names:
            storage.delete(name)

    transaction.on_commit(delete_files)

"""Reviews after a done job, in both directions (#38, docs/specs/reviews.md)."""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class WorkerTag(models.TextChoices):
    """What went well, said by the employer about the worker (R2, D2). Positive only."""

    ON_TIME = "on_time", _("On time")
    CAREFUL_WORK = "careful_work", _("Careful work")
    HARD_WORKING = "hard_working", _("Hard-working")
    CLEAN_SITE = "clean_site", _("Left the site clean")
    SAFETY_RULES = "safety_rules", _("Followed safety rules")


class EmployerTag(models.TextChoices):
    """What went well, said by the worker about the employer (R2, D2). Positive only."""

    PAID_ON_TIME = "paid_on_time", _("Paid in full and on time")
    AS_DESCRIBED = "as_described", _("Job as described")
    SAFE_WORKPLACE = "safe_workplace", _("Safe workplace")
    CLEAR_INSTRUCTIONS = "clear_instructions", _("Clear instructions")
    RESPECTFUL = "respectful", _("Respectful")


class Review(models.Model):
    """One side's rating of the other for one accepted application of a done job (R1).

    The worker rates the employer, the employer rates the worker (a crew is one account,
    so one review, D7). Which side wrote it follows from `author`. It cannot be changed
    (D6): no edit page, and the admin of #45 only removes.
    """

    application = models.ForeignKey(
        "jobs.Application",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("application"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
        verbose_name=_("author"),
    )
    rating = models.PositiveSmallIntegerField(
        _("rating"), validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    # The tag values, as WorkerProfile.skills (D2); which list is allowed depends on the
    # side, so ReviewForm checks it, not the model.
    tags = ArrayField(
        models.CharField(
            max_length=20, choices=WorkerTag.choices + EmployerTag.choices
        ),
        blank=True,
        default=list,
        verbose_name=_("tags"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        constraints = (
            # In the database, not only in the form: two tabs that post at the same
            # moment both pass the form's check, the second insert fails here (D8).
            models.UniqueConstraint(
                fields=["application", "author"], name="review_one_per_side"
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_1_to_5",
            ),
        )

    def __str__(self):
        return f"{self.rating}★ by {self.author} on {self.application}"

    @property
    def is_visible(self):
        """Whether the other side may see it yet (R6, D3).

        Hidden until the other side of the same application has rated too, so nobody
        rates in revenge; after the review deadline shown anyway. Computed when read, so
        no scheduled job has to open the reviews on day 14.
        """
        # >=: the moment can_review closes, this opens; no instant where both say no.
        if timezone.now() >= self.application.review_deadline:
            return True
        others = self.application.reviews.exclude(author_id=self.author_id)
        return others.exists()

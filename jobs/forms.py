"""Job forms: an employer posts or edits a job (#16); workers filter the job list (#18);
job photos, one in the admin and several on the edit page (#64).
"""

from datetime import timedelta
from typing import override

from django import forms
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.models import Skill

from .models import MINIMUM_WAGE, District, Job, JobPhoto, minimum_wage_on
from .photos import prepare_photo


class JobForm(forms.ModelForm):
    """Post or edit a job. Owner and status are not in the form: the view and model set them.

    Besides the model validators it checks that the date is not in the past and that the
    hourly rate is at least the minimum wage of the job's date (docs/specs/job-form.md R7).
    """

    class Meta:
        model = Job
        # The order of the UI mockup "Post a job". No original_language: the view takes the
        # employer's language, translation (#32) corrects it (spec D8).
        fields = (
            "job_type",
            "description",
            "address",
            "district",
            "date",
            "start_time",
            "hours",
            "workers_needed",
            "hourly_rate",
        )
        # RUF012 is wrong here: Django only reads these dicts when it builds the form class.
        labels = {"hourly_rate": _("Hourly rate, €")}  # noqa: RUF012
        help_texts = {  # noqa: RUF012
            # The only free text of a job: everything else is a key or a number, shown in
            # the reader's language anyway.
            "description": _("Write in your language. Workers read it in theirs."),
        }
        widgets = {  # noqa: RUF012
            # The class is set here, because daisyUI styles the <textarea> itself.
            "description": forms.Textarea(
                attrs={"rows": 4, "class": "textarea w-full"}
            ),
            # type="date" / "time" make phones show a date or time picker. The browser sends
            # and expects ISO values (2026-11-03, 08:00), whatever the page language.
            "date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        """Give the browser the same limits as the server (idea from #15).

        Set after the fields are built: Django would otherwise put its own min="0" on the
        number fields. "Today" is read here, on every request, not once at server start.
        """
        super().__init__(*args, **kwargs)
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
        for name in ("hours", "workers_needed"):
            self.fields[name].widget.attrs.update(min=1, max=10)
        self.fields["hourly_rate"].widget.attrs["min"] = MINIMUM_WAGE

    def clean_date(self):
        """A job cannot be posted for a day that is over (Munich time)."""
        day = self.cleaned_data["date"]
        if day < timezone.localdate():
            raise forms.ValidationError(_("The date cannot be in the past."))
        return day

    @override
    def clean(self):
        """The hourly rate must reach the minimum wage of the job's own date (#95, #17)."""
        cleaned_data = super().clean()
        day = cleaned_data.get("date")
        rate = cleaned_data.get("hourly_rate")
        # Missing when that field has its own error already; then there is nothing to compare.
        if day is not None and rate is not None:
            wage = minimum_wage_on(day)
            if rate < wage:
                self.add_error(
                    "hourly_rate",
                    _("At least %(wage)s € on this date (German minimum wage).")
                    % {"wage": wage},
                )
        return cleaned_data


class JobFilterForm(forms.Form):
    """The filters above the job list: date, job type, district (#18, docs/specs/job-list.md).

    The one place where the filters live (spec D10): the view, and later the map (#42), only
    call filter(). Read from the address (?district=sendling), so it saves nothing; an empty
    value means "all".
    """

    date = forms.ChoiceField(
        choices=[
            ("", _("Any day")),
            ("7", _("Next 7 days")),
            ("30", _("Next 30 days")),
        ],
        required=False,
        label=_("Date"),
    )
    job_type = forms.ChoiceField(
        choices=[
            ("", _("All types")),
        ]
        + Skill.choices,
        required=False,
        label=_("Job type"),
    )
    district = forms.ChoiceField(
        choices=[
            ("", _("All districts")),
        ]
        + District.choices,
        required=False,
        label=_("District"),
    )

    def filter(self, queryset):
        """The jobs of `queryset` that match the chosen filters, in the same order."""
        # Not "if self.is_valid()": with ?district=moon the form is invalid, but
        # cleaned_data still holds the fields that are valid, and those must still apply.
        # The value that is not in a list is simply missing there (spec R16).
        self.is_valid()
        date_filter = self.cleaned_data.get("date")
        job_type_filter = self.cleaned_data.get("job_type")
        district_filter = self.cleaned_data.get("district")

        # So a date here is "7" or "30", never another value (#21: the old else was dead).
        if date_filter:
            # "Next 7 days" is today and the 6 days after it (spec R14, D12).
            today = timezone.localdate()
            end_date = today + timedelta(days=int(date_filter) - 1)
            queryset = queryset.filter(date__range=(today, end_date))

        if job_type_filter:
            queryset = queryset.filter(job_type=job_type_filter)

        if district_filter:
            queryset = queryset.filter(district=district_filter)

        return queryset

    @property
    def has_filters(self):
        """True if at least one valid filter is chosen; "Reset filters" is shown then."""
        self.is_valid()
        return any(
            [
                self.cleaned_data.get("date"),
                self.cleaned_data.get("job_type"),
                self.cleaned_data.get("district"),
            ]
        )


class JobPhotoForm(forms.ModelForm):
    """One photo; the uploaded file is checked and prepared by prepare_photo() (#64, D3).

    Used by the admin's photo inline now; the job form (iteration 2) prepares its photos with
    the same function.
    """

    class Meta:
        model = JobPhoto
        fields = ("image",)  # the job comes from the page (inline) or the view

    def clean_image(self):
        """Replace the upload by the resized JPEG without EXIF, or show why it is refused."""
        return prepare_photo(self.cleaned_data["image"])


class MultipleFileInput(forms.FileInput):
    """A file input that lets the browser pick several files (the multiple attribute)."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A file field that cleans a list of files (recipe from the Django docs, #64 D12).

    Django has no field for several files: a FileField cleans one. This one cleans each file
    of the list the same way and returns the list.
    """

    def __init__(self, *args, **kwargs):
        """Use the multiple-file input unless the caller gives another widget."""
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    @override
    def clean(self, data, initial=None):
        """Clean every file; no file at all gives the "required" error of a single field."""
        clean_one = super().clean  # FileField's check of a single file
        if isinstance(data, list | tuple) and data:
            return [clean_one(file, initial) for file in data]
        # Nothing chosen comes as []: the single-file check turns it into "required".
        return [clean_one(data, initial)]


class JobPhotosForm(forms.Form):
    """Add several photos to one job on its edit page (docs/specs/job-photos.md R16).

    All or nothing (D17): one bad file or one photo too many makes the whole form invalid,
    and save() stores none of them.
    """

    photos = MultipleFileField(
        label=_("Photos"),
        widget=MultipleFileInput(
            attrs={
                # The browser's file picker shows only these; the server still checks.
                "accept": "image/jpeg,image/png,image/webp",
                "class": "file-input w-full",
            }
        ),
        error_messages={"required": _("Choose at least one photo.")},
    )

    def __init__(self, *args, job, **kwargs):
        """The job the photos are for: its photo count limits how many more fit."""
        super().__init__(*args, **kwargs)
        self.job = job

    def clean_photos(self):
        """Check the count, then prepare every file; the first problem stops the batch."""
        files = self.cleaned_data["photos"]
        free = Job.MAX_PHOTOS - self.job.photos.count()
        if len(files) > free:
            raise forms.ValidationError(
                ngettext(
                    "You can add %(count)d more photo.",
                    "You can add %(count)d more photos.",
                    free,
                )
                % {"count": free}
            )
        prepared = []
        for file in files:
            try:
                prepared.append(prepare_photo(file))
            except forms.ValidationError as error:
                # Several files in one go: say which one is wrong.
                raise forms.ValidationError(
                    _("%(name)s: %(error)s")
                    % {"name": file.name, "error": error.messages[0]}
                ) from None
        return prepared

    def save(self):
        """Store the prepared photos for the job; returns the new JobPhoto rows."""
        # One transaction: if one row fails, no row of the batch stays (D17).
        with transaction.atomic():
            return [
                JobPhoto.objects.create(job=self.job, image=photo)
                for photo in self.cleaned_data["photos"]
            ]

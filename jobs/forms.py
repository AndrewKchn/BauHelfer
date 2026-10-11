"""The job form: an employer posts or edits a job (#16)."""

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import MINIMUM_WAGE, Job, minimum_wage_on


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

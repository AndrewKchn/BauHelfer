"""Job forms: an employer posts or edits a job (#16); workers filter the job list (#18)."""

from datetime import timedelta

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Skill

from .models import MINIMUM_WAGE, District, Job, minimum_wage_on


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

        if date_filter:
            today = timezone.localdate()
            if date_filter == "7":
                end_date = today + timedelta(days=6)
            elif date_filter == "30":
                end_date = today + timedelta(days=29)
            else:
                end_date = None
            if end_date:
                # "Next 7 days" is today and the 6 days after it (spec R14, D12).
                queryset = queryset.filter(date__range=(today, end_date))

        if job_type_filter and job_type_filter != "":
            queryset = queryset.filter(job_type=job_type_filter)

        if district_filter and district_filter != "":
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

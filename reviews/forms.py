"""The review form (#38, docs/specs/reviews.md R8)."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Review


class ReviewForm(forms.ModelForm):
    """Stars (required) and the tags of one side's list (optional, D2).

    No application or author field: the view sets both from the URL and the login, so
    nobody can post a review in someone else's name.
    """

    # Radio buttons 1-5 instead of the number field a PositiveSmallIntegerField gets; the
    # template draws them as stars (D12). coerce=int: the model gets 4, not "4".
    rating = forms.TypedChoiceField(
        label=_("Rating"),
        choices=[(stars, stars) for stars in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect,
    )
    # Checkboxes instead of the ArrayField's comma-separated text box, as for skills. The
    # choices come from the view: the worker rates the employer, and the other way round.
    tags = forms.MultipleChoiceField(
        label=_("What went well? (optional)"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox"}),
    )

    class Meta:
        model = Review
        fields = ("rating", "tags")

    def __init__(self, *args, tag_choices, **kwargs):
        """Offer only `tag_choices`: a tag of the other list is then an invalid choice."""
        super().__init__(*args, **kwargs)
        self.fields["tags"].choices = tag_choices

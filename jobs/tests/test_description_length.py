"""Unit tests: a job description is at most 1000 characters (#34).

Spec: docs/specs/ai-translation.md, "#34: API errors and cost limits", iteration 2 (R18,
R19, D16, D22), acceptance criteria AC20, AC21. The form is JobForm, used both to post and
to edit a job; the pages are in test_description_length_views.py, the help text (R19) in
test_forms.py.
"""

import pytest

from jobs.forms import JobForm
from jobs.models import Job

from .test_forms import form_data

# django_db: the form runs the model's CheckConstraints, and Django checks them with a query.
pytestmark = [pytest.mark.django_db, pytest.mark.story(34)]


def test_description_of_1000_characters_is_valid():
    """A description of exactly 1000 characters is accepted (AC20).

    1. Fill in the job form with a description of 1000 characters
    2. Expect: the form is valid
    """
    form = JobForm(data=form_data(description="x" * 1000))

    assert form.is_valid(), form.errors


def test_description_of_1001_characters_is_refused():
    """A description of 1001 characters is refused with Django's length error (AC20).

    1. Fill in the job form with a description of 1001 characters
    2. Expect: the form is invalid, with the error "at most 1000 characters (it has 1001)"
    """
    form = JobForm(data=form_data(description="x" * 1001))

    assert not form.is_valid()
    [error] = form.errors["description"]
    assert "at most 1000 characters (it has 1001)" in error


def test_model_field_allows_1000_characters():
    """The limit is on the model field, so every form of a job gets it (R18, D22).

    1. Read Job.description
    2. Expect: max_length 1000, still a TextField (the column type does not change)
    """
    field = Job._meta.get_field("description")

    assert field.max_length == 1000
    assert field.get_internal_type() == "TextField"


def test_textarea_stops_typing_at_1000_characters():
    """The browser stops typing at 1000 characters: the textarea has maxlength (AC21).

    1. Render the description field of an empty job form
    2. Expect: maxlength="1000" on the textarea
    """
    assert 'maxlength="1000"' in str(JobForm()["description"])

"""Unit tests: the phone number must be one an employer can call from a mobile phone (#109).

The number starts with + and a country code, or with 0 and a German network / area code;
after that only digits, spaces and - / ( ), 10-15 digits in total. It is stored as entered.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.forms import NameAndPhoneForm
from accounts.validators import validate_phone

pytestmark = pytest.mark.story(109)

User = get_user_model()


@pytest.mark.parametrize(
    "number",
    [
        "+49 151 12345678",  # German mobile, international
        "0151 12345678",  # German mobile, national
        "089 1234567",  # Munich landline, 10 digits
        "+48 512 345 678",  # Polish mobile
        "+40 721 234 567",  # Romanian mobile
        "0151-123/456 78",  # all allowed separators
        "+49 (89) 1234567",  # brackets around the area code
        "+49151123456789",  # 15 digits, the E.164 maximum
    ],
)
def test_callable_numbers_are_accepted(number):
    """Numbers with a country or area code pass the check.

    1. Check a number with + and a country code, or with 0 and an area code
    2. Expect: no error
    """
    validate_phone(number)


@pytest.mark.parametrize(
    "number",
    [
        "abc",
        "call my brother",
        "151 12345678",  # no code at all
        "1234567890",  # no code at all
        "00 49 151 12345678",  # 00 instead of +
        "+0 151 12345678",  # country codes never start with 0
        "0 151 12345678",  # 0 alone is not an area code
        "089 12345",  # 8 digits, too short
        "+49 151 1234567890123",  # 18 digits, longer than E.164 allows
        "+49 151 1234.5678",  # a dot is not allowed
        "+49 151 12345678 ext 5",  # letters after the number
        "+49 151 12345678+",  # + only at the start
    ],
)
def test_other_numbers_are_rejected(number):
    """Text, numbers without a code and wrong lengths are rejected.

    1. Check text, a number without a code, a too short or too long number
    2. Expect: a ValidationError
    """
    with pytest.raises(ValidationError):
        validate_phone(number)


def test_error_message_shows_both_formats():
    """The error shows an example with a country code and one with an area code.

    1. Check the number "abc"
    2. Expect: the error contains "+49 151 12345678" and "0151 12345678"
    """
    with pytest.raises(ValidationError) as error:
        validate_phone("abc")

    message = error.value.messages[0]
    assert "+49 151 12345678" in message
    assert "0151 12345678" in message


@pytest.mark.django_db
def test_model_checks_the_phone():
    """The check is on the model field, so every form (and the admin) uses it.

    1. Build a user with the phone "abc" and run the model checks
    2. Expect: a ValidationError on phone
    """
    user = User(email="worker@example.com", phone="abc")
    user.set_unusable_password()

    with pytest.raises(ValidationError) as error:
        user.full_clean()

    assert "phone" in error.value.message_dict


@pytest.mark.django_db
def test_form_rejects_a_wrong_phone():
    """The profile form shows an error for a phone without a code.

    1. Submit the name and phone form with the phone "151 12345678"
    2. Expect: the form is invalid with an error on phone only
    """
    form = NameAndPhoneForm({"name": "Ivan", "phone": "151 12345678"})

    assert not form.is_valid()
    assert list(form.errors) == ["phone"]


@pytest.mark.django_db
def test_phone_is_stored_as_entered():
    """The number is saved exactly as typed, not reformatted.

    1. Submit the form with the phone "0151-123/456 78" and save it
    2. Expect: the saved phone is "0151-123/456 78"
    """
    user = User.objects.create_user(email="worker@example.com", password="x")
    form = NameAndPhoneForm({"name": "Ivan", "phone": "0151-123/456 78"}, instance=user)

    assert form.is_valid(), form.errors
    form.save()

    user.refresh_from_db()
    assert user.phone == "0151-123/456 78"


@pytest.mark.django_db
def test_phone_stays_optional():
    """An empty phone is still fine.

    1. Submit the form with a name and an empty phone
    2. Expect: the form is valid
    """
    form = NameAndPhoneForm({"name": "Ivan", "phone": ""})

    assert form.is_valid(), form.errors


def test_phone_field_is_a_tel_input():
    """The phone field opens the number keyboard on phones.

    1. Render the phone field of an empty name and phone form
    2. Expect: type="tel"
    """
    html = str(NameAndPhoneForm()["phone"])

    assert 'type="tel"' in html


def test_phone_field_shows_both_formats_as_examples():
    """A hint under the field shows an example of each format.

    1. Open an empty name and phone form
    2. Expect: the phone help text says "For example" and shows both formats
    """
    help_text = str(NameAndPhoneForm().fields["phone"].help_text)

    assert help_text.startswith("For example")
    assert "+49 151 12345678" in help_text
    assert "0151 12345678" in help_text

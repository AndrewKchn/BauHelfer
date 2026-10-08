"""Checks for user data that Django has no built-in validator for."""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# + and a country code, or 0 and a German network / area code. Neither code starts with 0
# (00 is the international prefix). After that only digits, spaces and - / ( ).
PHONE_PATTERN = re.compile(r"[+0][1-9][0-9 \-/()]*")
# 15 digits is the maximum of the international standard E.164.
PHONE_DIGITS = range(10, 16)


def validate_phone(value):
    """Reject a phone number an employer could not call from a mobile phone (#109).

    Only the format is checked; the number is stored as entered, not reformatted.
    """
    digits = len(re.findall(r"[0-9]", value))
    if not PHONE_PATTERN.fullmatch(value) or digits not in PHONE_DIGITS:
        raise ValidationError(
            _(
                "Enter the number with a country code, e.g. +49 151 12345678, "
                "or with an area code, e.g. 0151 12345678."
            ),
            code="invalid_phone",
        )

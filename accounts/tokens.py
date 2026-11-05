"""The token in the email confirmation link (#81, docs/specs/email-verification.md D5)."""

from typing import override

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Django's password reset token, made for confirming an address.

    Nothing is stored: the token is a time and a signature of the user's data. Django checks
    it by signing the data again, so it fails once the data changes, and after
    PASSWORD_RESET_TIMEOUT.
    """

    # Another salt gives other signatures: a reset link does not confirm an address, and
    # a confirmation link does not reset a password.
    key_salt = "accounts.tokens.EmailVerificationTokenGenerator"

    @override
    def _make_hash_value(self, user, timestamp):
        """Django's data plus the confirmation date: after the click the link is used up."""
        return f"{super()._make_hash_value(user, timestamp)}{user.email_verified_at}"


email_verification_token = EmailVerificationTokenGenerator()

"""The email with the confirmation link (#81, docs/specs/email-verification.md R3)."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token

logger = logging.getLogger(__name__)


def send_verification_email(request, user):
    """Email `user` the link that confirms their address, in the page's language (D8).

    The only email that goes to an unconfirmed address: it is how the address gets
    confirmed. A failed send is logged and never stops the signup (D9).
    """
    path = reverse(
        "verify_email",
        args=[
            urlsafe_base64_encode(force_bytes(user.pk)),  # the id, safe for a URL
            email_verification_token.make_token(user),
        ],
    )
    context = {
        "link": request.build_absolute_uri(path),  # read outside the site: full address
        "days": settings.PASSWORD_RESET_TIMEOUT // (24 * 60 * 60),
    }
    # One line: the template file ends with a line break, and a header must not have one.
    subject = " ".join(render_to_string("emails/verify_email_subject.txt").split())
    body = render_to_string("emails/verify_email_body.txt", context)
    try:
        send_mail(subject, body, None, [user.email])  # None: DEFAULT_FROM_EMAIL
    # Every backend raises its own errors; as for the notifications (#27, D10), all are
    # caught and logged with the class only: a provider's error text can hold the address.
    except Exception as error:  # noqa: BLE001
        logger.error(
            "Verification email failed: user_id=%s error=%s",
            user.pk,
            type(error).__name__,
        )
    else:
        # Only after a real send: after a failure the user may try again at once (R10).
        user.verification_sent_at = timezone.now()
        user.save(update_fields=["verification_sent_at"])

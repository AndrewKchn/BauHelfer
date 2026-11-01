"""Emails about applications: a new one to the employer, the decision to the worker (#27).

docs/specs/notifications.md. The views call these after the change is saved (D5). Each
email is rendered in the recipient's language (D8); a failed email is logged and never
undoes the action (D10).
"""

import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation

from .models import Application

logger = logging.getLogger(__name__)


def notify_new_application(request, application):
    """Email the job's employer, with a link to the application on the job page (R5)."""
    url = reverse("job_detail", args=[application.job_id])
    path = f"{url}#application-{application.pk}"
    send(request, application, "new_application", application.job.employer, path)


def notify_decision(request, application):
    """Email the worker whether their application was accepted or rejected (R5)."""
    if application.status == Application.Status.ACCEPTED:
        kind, path = "application_accepted", reverse("my_applications")
    else:
        kind, path = "application_rejected", reverse("home")
    send(request, application, kind, application.worker, path)


def send(request, application, kind, recipient, path):
    """Render emails/<kind>_subject.txt and _body.txt for `recipient` and send them.

    Nothing at all to an address that is not confirmed (R20, D13), or to a recipient who
    turned the emails off (R12). `path` is the page the email points to; the links get the
    site's address, as the email is read outside it (R6).
    """
    if not recipient.email_verified_at or not recipient.email_notifications:
        return
    context = {
        "application": application,
        "job": application.job,
        "recipient": recipient,  # "Hello <name>," in emails/_greeting.txt
        "link": request.build_absolute_uri(path),
        # The recipient's own profile form, with the checkbox (R13, D4), in _footer.txt.
        "settings_link": request.build_absolute_uri(recipient.get_profile_url()),
    }
    # The recipient's language only while rendering; the request's comes back after (R3).
    with translation.override(recipient.preferred_language):
        subject = render_to_string(f"emails/{kind}_subject.txt", context)
        body = render_to_string(f"emails/{kind}_body.txt", context)
    # One line: the template file ends with a line break, and a header must not have one.
    subject = " ".join(subject.split())
    try:
        send_mail(subject, body, None, [recipient.email])  # None: DEFAULT_FROM_EMAIL
    # Every backend raises its own errors (network, refused, over the limit); none of them
    # may undo the saved action (D10), so all of them are caught.
    except Exception as error:  # noqa: BLE001
        # The class only: the error text of a provider can hold the address (D10).
        logger.error(
            "Notification failed: kind=%s application_id=%s error=%s",
            kind,
            application.pk,
            type(error).__name__,
        )
    else:
        logger.info(
            "Notification sent: kind=%s application_id=%s", kind, application.pk
        )

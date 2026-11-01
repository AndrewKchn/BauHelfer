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
    link = request.build_absolute_uri(f"{url}#application-{application.pk}")
    send(application, "new_application", application.job.employer, link)


def notify_decision(request, application):
    """Email the worker whether their application was accepted or rejected (R5)."""
    if application.status == Application.Status.ACCEPTED:
        kind, url = "application_accepted", reverse("my_applications")
    else:
        kind, url = "application_rejected", reverse("home")
    send(application, kind, application.worker, request.build_absolute_uri(url))


def send(application, kind, recipient, link):
    """Render emails/<kind>_subject.txt and _body.txt for `recipient` and send them.

    `link` is already absolute: the email is read outside the site (R6).
    """
    context = {
        "application": application,
        "job": application.job,
        "recipient": recipient,  # "Hello <name>," in emails/_greeting.txt
        "link": link,
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

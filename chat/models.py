"""The chat of an accepted application (#35, docs/specs/chat.md R1, R3)."""

from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _


class Message(models.Model):
    """One message of the worker or the employer in the chat of an application.

    Who may write and read is decided by Application.chat_writable / chat_readable; the
    database only stores what the view let through.
    """

    application = models.ForeignKey(
        "jobs.Application",
        on_delete=models.CASCADE,  # the chat goes with its application
        related_name="messages",  # application.messages.all()
        verbose_name=_("application"),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",  # not "messages": that name means Django's messages
        verbose_name=_("sender"),
    )
    # varchar(1000): even code that skips the form cannot save more; the limit of a text
    # the translation takes (#34), so #36 can translate every message (D5).
    text = models.CharField(_("text"), max_length=1000)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        # Oldest first, as the chat is read; the id decides between two equal times.
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.sender}: {self.text[:30]}"


def with_has_messages(applications):
    """Add `has_messages` to every application of the queryset, in the same query (R3, R11).

    EXISTS (SELECT … WHERE application_id = <this row's id>): True or False per row, so a
    list of applications can ask chat_readable without one query per card. A function
    here, not a method of Application: jobs would have to import chat, which imports jobs.
    """
    return applications.annotate(
        has_messages=Exists(Message.objects.filter(application=OuterRef("pk")))
    )

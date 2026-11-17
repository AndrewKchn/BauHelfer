"""The chat of an accepted application (#35, docs/specs/chat.md R1, R3)."""

from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
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
    # When the other person first saw it; empty = unread (#35, chat.md R19, D15). Set by
    # ChatView when it draws the page (R20, D17), never by a form.
    read_at = models.DateTimeField(_("read at"), null=True, blank=True, editable=False)

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


def unread_count(user):
    """How many messages wait for `user`: in their chats, not their own, not read (R21).

    "Their chats": the applications where they are the worker or the employer of the job.
    One COUNT query; the context processor runs it on every page (D18).
    """
    return (
        Message.objects.filter(
            Q(application__worker=user) | Q(application__job__employer=user),
            read_at=None,
        )
        .exclude(sender=user)
        .count()
    )

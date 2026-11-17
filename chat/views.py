"""The chat page of an application (#35, docs/specs/chat.md R4-R10)."""

from typing import override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.views import View
from django.views.generic import ListView

from jobs.models import Application
from jobs.views import original_id
from translations.services import detect_language, translate

from .forms import MessageForm
from .models import Message, with_has_messages
from .shown_text import chat_messages_for, chat_previews_for


def other_side(application, user):
    """The person `user` chats with in `application`: the employer or the worker."""
    if user == application.worker:
        return application.job.employer
    return application.worker


class ChatView(LoginRequiredMixin, View):
    """GET: the messages and the form; POST: send one (R4-R6).

    Only the application's worker and its job's employer: anyone else gets 404, as does a
    participant when the chat is not readable (D4). Any role: both sides use the same page.
    """

    template_name = "chat/chat.html"

    def get_application(self):
        """The application of the URL, if the user takes part in it and may read its chat.

        The filter is in the query: another user's application is "not found", the same
        answer as one that does not exist, so the page does not tell that it exists.
        """
        user = self.request.user
        applications = with_has_messages(
            Application.objects.select_related("job__employer", "worker").filter(
                Q(worker=user) | Q(job__employer=user)
            )
        )
        application = get_object_or_404(applications, pk=self.kwargs["pk"])
        if not application.chat_readable:
            raise Http404
        return application

    def get(self, request, *args, **kwargs):
        """The chat with an empty form; 204 to an ask with nothing new (R14-R16, D11).

        The open chat asks every 4 seconds with ?after=<its last message id>. Nothing newer:
        an empty 204, on which HTMX changes nothing, so a quiet chat costs no page. Anything
        else, also an ?after= that is not a number, gets the whole page. The access check
        comes first: a stranger's ask is a 404 too.
        """
        application = self.get_application()
        after = request.GET.get("after", "")
        if after.isdecimal() and not application.messages.filter(pk__gt=after).exists():
            return HttpResponse(status=204)
        return self.show(application, MessageForm())

    def post(self, request, *args, **kwargs):
        """Save the message, then back to the chat (Post/Redirect/Get, R6).

        A reload after the redirect repeats the GET, not the POST, so nothing is sent
        twice. A closed chat takes nothing: 404, as for a stranger.
        """
        application = self.get_application()
        if not application.chat_writable:
            raise Http404
        form = MessageForm(request.POST)
        if not form.is_valid():
            return self.show(application, form)
        form.instance.application = application
        form.instance.sender = request.user
        # The text's language (#36, chat-translation.md R2, D3): Claude finds it; when it
        # cannot tell, the sender's site language.
        language = detect_language(form.cleaned_data["text"])
        form.instance.original_language = (
            request.user.preferred_language if language is None else language
        )
        message = form.save()
        # Translated now, into the other person's language, so their page and polls read
        # it from the cache (R3, D1): the sender waits once, the reader never. The result is
        # not needed here; translate() never raises, so a failure still sends (D10).
        other_language = other_side(application, request.user).preferred_language
        if message.original_language != other_language:
            translate(message.text, other_language)
        return redirect("chat", application.pk)

    def show(self, application, form):
        """Render the page: who is on the other side and where "back" leads (R7).

        Drawing the messages is reading them: the other person's unread ones are marked read
        first, in one UPDATE (R20, D17), so the navigation badge of this very page no
        longer counts them. A 204 never comes here, so it marks nothing.
        """
        user = self.request.user
        application.messages.filter(read_at=None).exclude(sender=user).update(
            read_at=timezone.now()
        )
        other = other_side(application, user)
        if user == application.worker:
            back_url = reverse("my_applications")
        else:
            job_url = reverse("job_detail", args=[application.job.pk])
            back_url = f"{job_url}#application-{application.pk}"
        # One query for the messages, one for their cached translations (#36, R4, R5):
        # each gets `shown`, its text as this reader should see it, in the active language
        # (job-translation.md R8). ?original=<id> is the "Show original" link of one
        # message (R12, D8); an id of another chat matches nothing here. The template
        # tells own messages by sender_id.
        chat_messages = chat_messages_for(
            application.messages.all(),
            user,
            translation.get_language(),
            original_id=original_id(self.request),
        )
        context = {
            "application": application,
            "job": application.job,
            "chat_messages": chat_messages,
            # What the open chat sends as ?after= when it asks (R13): 0 before the first.
            "last_id": chat_messages[-1].pk if chat_messages else 0,
            "form": form,
            "other": other,
            "back_url": back_url,
        }
        return render(self.request, self.template_name, context)


class ChatListView(LoginRequiredMixin, ListView):
    """Every chat the user can read, newest activity first (R24, D16, D20).

    One query for all rows, however many: the other person and the job come with
    select_related; the last message, the time of the last activity and the unread count are
    computed by the database for every row (R25).
    """

    template_name = "chat/chat_list.html"
    context_object_name = "chats"

    @override
    def get_queryset(self):
        """All the user's applications, as worker or as employer, with their chat data.

        Which of them have a chat is decided by chat_readable in get_context_data: the one
        rule of R3, not a second copy of it in SQL. has_messages comes with the rows, so it
        costs no query per row.
        """
        user = self.request.user
        last_message = Message.objects.filter(application=OuterRef("pk")).order_by(
            "-created_at", "-id"
        )
        return (
            with_has_messages(
                Application.objects.filter(Q(worker=user) | Q(job__employer=user))
            )
            .select_related("job__employer", "worker")
            .annotate(
                # The text of the newest message (D21): a subquery per row, run by the
                # database inside the same query.
                last_text=Subquery(last_message.values("text")[:1]),
                # Its language and sender, for the preview in the reader's language
                # (#36, chat-translation.md R14, D11): in the same query, as last_text.
                last_language=Subquery(last_message.values("original_language")[:1]),
                last_sender_id=Subquery(last_message.values("sender_id")[:1]),
                # The newest message, or the application itself before the first (D20).
                activity=Coalesce(Max("messages__created_at"), "created_at"),
                # Only the other person's unread messages (as unread_count, R21).
                unread=Count(
                    "messages",
                    filter=Q(messages__read_at=None) & ~Q(messages__sender=user),
                ),
            )
            .order_by("-activity", "-pk")
        )

    @override
    def get_context_data(self, **kwargs):
        """Keep the readable chats only, name the other person of each (R24) and give each
        its last message in the reader's language (#36, R15, one query for all).
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        chats = [chat for chat in context["chats"] if chat.chat_readable]
        for chat in chats:
            chat.other = other_side(chat, user)
        context["chats"] = chat_previews_for(chats, user, translation.get_language())
        return context

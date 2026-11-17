"""The chat page of an application (#35, docs/specs/chat.md R4-R10)."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from jobs.models import Application

from .forms import MessageForm
from .models import with_has_messages


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
        form.save()
        return redirect("chat", application.pk)

    def show(self, application, form):
        """Render the page: who is on the other side and where "back" leads (R7)."""
        if self.request.user == application.worker:
            other = application.job.employer
            back_url = reverse("my_applications")
        else:
            other = application.worker
            job_url = reverse("job_detail", args=[application.job.pk])
            back_url = f"{job_url}#application-{application.pk}"
        # One query: the template tells own messages by sender_id, no user needed.
        chat_messages = list(application.messages.all())
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

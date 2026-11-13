"""The review page of an application (#38, docs/specs/reviews.md R7-R9)."""

import logging
from typing import override

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import CreateView

from jobs.models import Application

from .forms import ReviewForm
from .models import EmployerTag, WorkerTag

logger = logging.getLogger(__name__)


class ReviewCreateView(LoginRequiredMixin, CreateView):
    """One side rates the other for one accepted application of a done job (R7, D4).

    The same page for both sides: the worker rates the employer, the employer rates the
    worker; the tags and where to go afterwards follow from who is logged in.
    """

    form_class = ReviewForm
    template_name = "reviews/review_form.html"

    def get_application(self):
        """The application from the URL, if the logged-in user may review it now (R7).

        can_review() is the one place that knows who may review: a stranger, and a side
        that cannot review now (not done, too late, already reviewed), get the same 404 as
        an unknown id, so nobody learns that the application exists (D10).
        """
        applications = Application.objects.select_related(
            "job__employer__employer_profile", "worker"
        )
        application = get_object_or_404(applications, pk=self.kwargs["pk"])
        if not application.can_review(self.request.user):
            raise Http404
        return application

    # As Django's UpdateView sets self.object in get() and post(): the application is
    # read once per request, after LoginRequiredMixin has sent guests to the login page.
    @override
    def get(self, request, *args, **kwargs):
        """Find the application, then show the empty form."""
        self.application = self.get_application()
        return super().get(request, *args, **kwargs)

    @override
    def post(self, request, *args, **kwargs):
        """Find the application, then check and save the form."""
        self.application = self.get_application()
        return super().post(request, *args, **kwargs)

    @property
    def by_worker(self):
        """Whether the logged-in user is the worker (else the employer) of the application."""
        return self.request.user.pk == self.application.worker_id

    @override
    def get_form_kwargs(self):
        """The tags of the rated side: the employer's for the worker, and back (R2)."""
        kwargs = super().get_form_kwargs()
        kwargs["tag_choices"] = (EmployerTag if self.by_worker else WorkerTag).choices
        return kwargs

    @override
    def get_context_data(self, **kwargs):
        """Who is rated, for the title and the hint (R8)."""
        context = super().get_context_data(**kwargs)
        job = self.application.job
        if self.by_worker:
            context["rated_name"] = job.employer.employer_profile.display_name
        else:
            context["rated_name"] = self.application.worker.name
        context["application"] = self.application
        context["job"] = job
        return context

    @override
    def form_valid(self, form):
        """Save the review for this application in the user's name (R8, R9).

        Two tabs may both have passed can_review; the database's unique constraint stops
        the second (D8). atomic(): the failed insert is undone on its own, so the request
        can still answer 404 instead of an error 500.
        """
        form.instance.application = self.application
        form.instance.author = self.request.user
        try:
            with transaction.atomic():
                response = super().form_valid(form)
        except IntegrityError:
            raise Http404 from None
        logger.info(
            "Review published: application_id=%s author_id=%s",
            self.application.pk,
            self.request.user.pk,
        )
        messages.success(self.request, _("Review published."))
        return response

    @override
    def get_success_url(self):
        """Back where the user came from: "My applications", "Done" tab, or the job (D4)."""
        if self.by_worker:
            return reverse("my_applications") + "#tab-done"
        return reverse("job_detail", args=[self.application.job.pk])

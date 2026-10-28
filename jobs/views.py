"""Job pages: the public job list (#18) and job page (#19, docs/specs/job-detail.md) with
the apply form (#22, docs/specs/application.md), and the employer pages: post, list own,
edit, cancel (#16, docs/specs/job-form.md), add and delete photos (#64,
docs/specs/job-photos.md). The job page shows its employer the applications (#23,
docs/specs/applications-list.md), who accepts or rejects them (#24,
docs/specs/accept-reject.md).
"""

import logging
from typing import override

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from accounts.models import User
from accounts.views import RoleRequiredMixin

from .forms import ApplicationForm, JobFilterForm, JobForm, JobPhotosForm
from .models import Application, ApplicationStateError, Job, JobPhoto

# "jobs.views". Ids only, never an email or other personal data (#124).
logger = logging.getLogger(__name__)


class EmployerRequiredMixin(RoleRequiredMixin):
    """Employers only: guests go to login, workers get 403 (spec R10)."""

    role = User.Role.EMPLOYER


class WorkerRequiredMixin(RoleRequiredMixin):
    """Workers only: guests go to login, employers get 403."""

    role = User.Role.WORKER


class OwnOpenJobMixin(EmployerRequiredMixin):
    """The page works on one of the logged-in employer's own open jobs (spec R12, D2, D7).

    get_object() looks the id from the URL up in this queryset only. Another employer's job,
    or a job that is not open, is not in it, so the answer is 404: the page does not even
    tell that such a job exists.
    """

    @override
    def get_queryset(self):
        """Only the logged-in employer's open jobs."""
        return self.request.user.jobs.open()


class EmployerProfileRequiredMixin:
    """No company profile yet: send the employer to the profile form first (spec D1).

    Listed after EmployerRequiredMixin, so its dispatch() runs after the login and role
    checks: a guest is sent to login, not to a profile form.
    """

    @override
    def dispatch(self, request, *args, **kwargs):
        """Redirect to the profile form if the employer has no profile; else go on."""
        if not hasattr(request.user, "employer_profile"):
            messages.info(
                request, _("Please fill in your company profile before posting a job.")
            )
            return redirect("employer_profile_edit")
        return super().dispatch(request, *args, **kwargs)


class JobCreateView(EmployerRequiredMixin, EmployerProfileRequiredMixin, CreateView):
    """Post a new job (spec R11), then add photos on its edit page (job-photos.md D10)."""

    form_class = JobForm
    template_name = "jobs/job_form.html"

    @override
    def form_valid(self, form):
        """Owner and language come from the login, never from the form (spec R6, D8)."""
        form.instance.employer = self.request.user
        # Translation (#32) starts from it and corrects it if the text is in another one.
        form.instance.original_language = self.request.user.preferred_language
        messages.success(self.request, _("Job posted. You can add photos below."))
        response = super().form_valid(form)  # saves the job and redirects
        logger.info(
            "Job created: job_id=%s employer_id=%s",
            self.object.pk,
            self.request.user.pk,
        )
        return response

    @override
    def get_success_url(self):
        """The new job's edit page, scrolled to the photo block (job-photos.md R12, R21)."""
        # Called after the save, so self.object has its id now. The browser jumps to the
        # element with id="photos"; the server never sees the "#photos" part.
        return reverse("job_edit", args=[self.object.pk]) + "#photos"


class MyJobsView(EmployerRequiredMixin, ListView):
    """The employer's own jobs in every status, soonest first (spec R14, D5)."""

    template_name = "jobs/my_jobs.html"
    context_object_name = "jobs"

    @override
    def get_queryset(self):
        """Only the logged-in employer's jobs, each with its number of applications."""
        return (
            self.request.user.jobs.annotate(applications_count=Count("applications"))
            .prefetch_related("photos")
            .order_by("date", "start_time")
        )

    @override
    def get_context_data(self, **kwargs):
        """One tab per status that has jobs, in the order of Job.Status."""
        context = super().get_context_data(**kwargs)
        jobs = context["jobs"]
        context["groups"] = [
            {"status": status, "label": label, "jobs": group}
            for status, label in Job.Status.choices
            if (group := [job for job in jobs if job.status == status])
        ]
        return context


class JobEditView(OwnOpenJobMixin, UpdateView):
    """Change one of the employer's own open jobs (spec R12)."""

    form_class = JobForm
    template_name = "jobs/job_form.html"
    success_url = reverse_lazy("my_jobs")

    @override
    def form_valid(self, form):
        """Save the changes and say so."""
        messages.success(self.request, _("Job saved."))
        return super().form_valid(form)

    @override
    def get_context_data(self, **kwargs):
        """Add the photo block: the job's photos and the empty upload form (job-photos R14)."""
        context = super().get_context_data(**kwargs)
        context["photos"] = self.object.photos.all()
        context["photo_form"] = JobPhotosForm(job=self.object)
        context["max_photos"] = Job.MAX_PHOTOS
        return context


class JobPhotoAddView(OwnOpenJobMixin, SingleObjectMixin, View):
    """POST: add the chosen photos to one of the employer's own open jobs (job-photos R16).

    Only POST (a GET gives 405). Success and errors both go back to the edit page as a
    message (D18): the edit page draws itself, this view does not rebuild it.
    """

    def post(self, request, *args, **kwargs):
        """Save all photos or none, say what happened, go back to the edit page."""
        job = self.get_object()  # 404 unless it is the employer's own open job
        form = JobPhotosForm(files=request.FILES, job=job)
        if form.is_valid():
            count = len(form.save())
            messages.success(
                request,
                ngettext("%(count)d photo added.", "%(count)d photos added.", count)
                % {"count": count},
            )
        else:
            for error in form.errors["photos"]:
                messages.error(request, error)
        return redirect("job_edit", pk=job.pk)


class JobPhotoDeleteView(EmployerRequiredMixin, SuccessMessageMixin, DeleteView):
    """POST: delete one photo of the employer's own open job at once (job-photos R17, D19).

    Django's DeleteView deletes on POST; GET would show a confirmation page, which we do
    not want, so only POST is allowed (GET gives 405). The file goes by the post_delete
    signal (R7).
    """

    http_method_names = ("post",)
    success_message = _("Photo deleted.")

    @override
    def get_queryset(self):
        """Only photos of the logged-in employer's open jobs; any other id gives 404."""
        return JobPhoto.objects.filter(job__in=self.request.user.jobs.open())

    @override
    def get_success_url(self):
        """Back to the job's edit page."""
        return reverse("job_edit", args=[self.object.job_id])


class JobCancelView(OwnOpenJobMixin, DetailView):
    """GET asks "cancel this job?", POST cancels it (spec R13, D6).

    Cancelling changes the status and keeps the row: the job stays in "My jobs", and the
    applications to it (#22) keep their job.
    """

    template_name = "jobs/job_confirm_cancel.html"
    context_object_name = "job"

    def post(self, request, *args, **kwargs):
        """Mark the job cancelled and go back to "My jobs"."""
        job = self.get_object()  # 404 unless it is the employer's own open job
        job.status = Job.Status.CANCELLED
        job.save(update_fields=["status"])
        logger.info("Job cancelled: job_id=%s employer_id=%s", job.pk, request.user.pk)
        messages.success(request, _("Job cancelled."))
        return redirect("my_jobs")


class JobListView(ListView):
    """The home page: open jobs that have not started yet, for everyone (#18, spec R1-R4).

    No login mixin: guests see the list too (spec D1).
    """

    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    # ListView reads ?page= and puts only that page's jobs into "jobs"; a page number that
    # does not exist gives 404 (spec R5, D3).
    paginate_by = 20

    @override
    def get_queryset(self):
        """Open jobs that have not started yet, soonest first, narrowed by the filters."""
        # Kept on the view for get_context_data(), which ListView calls after this method.
        # A new view object is made for every request, so one visitor's filters stay theirs.
        self.filter_form = JobFilterForm(self.request.GET)
        # prefetch_related: the photos of all jobs on the page in one more query, not one
        # query per card (job-photos.md R30, D28).
        # with_workers_found(): "Needs 1 worker" counts only the free places, from the same
        # query (accept-reject.md R14, R16).
        jobs = (
            Job.objects.open()
            .upcoming()
            .with_workers_found()
            .order_by("date", "start_time")
            .prefetch_related("photos")
        )
        return self.filter_form.filter(jobs)

    @override
    def get_context_data(self, **kwargs):
        """Add the filter form to what ListView gives the template (jobs, page_obj, ...)."""
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context


class JobDetailView(DetailView):
    """One job with everything about it, for everyone, in any status (#19, spec R1-R8, D1).

    No login mixin: guests see the page too. The address is shown only to the job's own
    employer (D4).
    """

    template_name = "jobs/job_detail.html"
    context_object_name = "job"
    # The employer and their profile come in the same query as the job (spec R12): the page
    # shows both, and without this each would cost a query of its own. The photos are one
    # more query, made by the template (R19).
    # with_workers_found(): "1 of 3 workers found" and the places left, in the same query
    # (accept-reject.md R12, R16).
    queryset = Job.objects.select_related(
        "employer__employer_profile"
    ).with_workers_found()

    @override
    def get_context_data(self, **kwargs):
        """Add who looks: the owner sees the address, "Edit" and the applications, a worker
        the apply part."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        job = self.object
        is_owner = user == job.employer
        context["is_owner"] = is_owner
        # Decided here, not in the template: #25 adds the worker whose application was
        # accepted, and the template stays as it is.
        context["show_address"] = is_owner
        if is_owner:
            # Only for the owner (applications-list.md D16): a guest's page keeps its 2
            # queries. select_related: each application's worker and profile come in the
            # same query, so 10 applications cost one query, not 21 (D7). The skills are an
            # array in the profile row and need no query of their own. Newest first (D5).
            context["applications"] = job.applications.select_related(
                "worker__worker_profile"
            ).order_by("-created_at")
            # The template picks "Accept 2" or "Accept 1 of 2" and the "fills the job"
            # warning with it (accept-reject.md R7, R8); loaded with the job, no query.
            context["places_left"] = job.places_left
        # Only for workers: a guest's page keeps its 2 queries (application.md AC11).
        if user.is_authenticated and user.role == User.Role.WORKER:
            # Their application, also when the job is closed now (D7); None if there is none.
            application = job.applications.filter(worker=user).first()
            context["application"] = application
            # Whether the job takes applications is checked by the template, around the form.
            if application is None and user.can_apply():
                # JobApplyView passes in the form with its errors; otherwise an empty one.
                context.setdefault("apply_form", ApplicationForm(job=job, worker=user))
        return context


class JobApplyView(WorkerRequiredMixin, JobDetailView):
    """POST: the apply form on the job page saves an application (#22, application.md R5).

    A JobDetailView, so a form with errors is shown on the same job page with everything on
    it (D1). Only POST (a GET gives 405), workers only (#19 R9).
    """

    http_method_names = ("post",)

    def post(self, request, *args, **kwargs):
        """Check that the worker may apply here, then save the form or show its errors."""
        # self.object: get_context_data() reads it when the page is shown again.
        job = self.object = self.get_object()  # 404 for a job id that does not exist
        worker = request.user
        # The page shows none of these cases a form; these checks stop a POST sent anyway.
        if not worker.can_apply():
            messages.error(request, _("Complete your profile to apply."))
            return redirect("job_detail", pk=job.pk)
        if not job.accepts_applications:
            messages.error(request, _("This job no longer takes applications."))
            return redirect("job_detail", pk=job.pk)
        if job.applications.filter(worker=worker).exists():
            messages.info(request, _("You have already applied to this job."))
            return redirect("job_detail", pk=job.pk)

        form = ApplicationForm(request.POST, job=job, worker=worker)
        if not form.is_valid():
            # The same page again, with the typed values and the errors.
            return self.render_to_response(self.get_context_data(apply_form=form))
        application = form.save()
        # Ids only: the message may hold a phone number or a name (#124, D9).
        logger.info(
            "Application created: application_id=%s job_id=%s worker_id=%s",
            application.pk,
            job.pk,
            worker.pk,
        )
        messages.success(request, _("Application sent."))
        return redirect("job_detail", pk=job.pk)


class OwnPendingApplicationMixin(EmployerRequiredMixin, SingleObjectMixin):
    """The page works on a pending application to one of the employer's own open jobs.

    accept-reject.md R5, D5. Like OwnOpenJobMixin: anything else is not in the queryset,
    so the answer is 404. The views have only post(), so a GET gives 405: a link must not
    decide.
    """

    @override
    def get_queryset(self):
        """Pending applications to the logged-in employer's open jobs."""
        return Application.objects.filter(
            job__employer=self.request.user,
            job__status=Job.Status.OPEN,
            status=Application.Status.PENDING,
        ).select_related("worker")


def back_to(application):
    """The job page, scrolled to this application (accept-reject.md R6, D8)."""
    url = reverse("job_detail", args=[application.job_id])
    return redirect(f"{url}#application-{application.pk}")


class ApplicationAcceptView(OwnPendingApplicationMixin, View):
    """POST: accept an application, part of a crew if fewer places are left (R3, R6)."""

    def post(self, request, *args, **kwargs):
        """Accept, say how many workers were taken and whether the job is filled now."""
        application = self.get_object()
        try:
            application.accept()
        except ApplicationStateError:
            # Another tab or a double tap decided it a moment earlier (D6).
            messages.info(request, _("This application was already decided."))
            return back_to(application)
        count = application.workers_accepted
        messages.success(
            request,
            ngettext(
                "Accepted: %(count)d worker from %(name)s.",
                "Accepted: %(count)d workers from %(name)s.",
                count,
            )
            % {"count": count, "name": application.worker.name},
        )
        logger.info(
            "Application accepted: application_id=%s job_id=%s employer_id=%s "
            "workers=%s",
            application.pk,
            application.job_id,
            request.user.pk,
            count,
        )
        if application.job.status == Job.Status.FILLED:
            messages.success(
                request,
                _("The job is filled. The other pending applications were closed."),
            )
            logger.info(
                "Job filled: job_id=%s employer_id=%s",
                application.job_id,
                request.user.pk,
            )
        return back_to(application)


class ApplicationRejectView(OwnPendingApplicationMixin, View):
    """POST: reject an application (R4, R6)."""

    def post(self, request, *args, **kwargs):
        """Reject and say so."""
        application = self.get_object()
        try:
            application.reject()
        except ApplicationStateError:
            messages.info(request, _("This application was already decided."))
            return back_to(application)
        messages.success(
            request,
            _("Rejected: %(name)s.") % {"name": application.worker.name},
        )
        logger.info(
            "Application rejected: application_id=%s job_id=%s employer_id=%s",
            application.pk,
            application.job_id,
            request.user.pk,
        )
        return back_to(application)

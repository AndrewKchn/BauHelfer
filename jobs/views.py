"""Job pages: the public job list (#18) and the employer pages: post, list own, edit,
cancel (#16, docs/specs/job-form.md).
"""

from typing import override

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.models import User
from accounts.views import RoleRequiredMixin

from .forms import JobFilterForm, JobForm
from .models import Job


class EmployerRequiredMixin(RoleRequiredMixin):
    """Employers only: guests go to login, workers get 403 (spec R10)."""

    role = User.Role.EMPLOYER


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
    """Post a new job (spec R11)."""

    form_class = JobForm
    template_name = "jobs/job_form.html"
    success_url = reverse_lazy("my_jobs")

    @override
    def form_valid(self, form):
        """Owner and language come from the login, never from the form (spec R6, D8)."""
        form.instance.employer = self.request.user
        # Translation (#32) starts from it and corrects it if the text is in another one.
        form.instance.original_language = self.request.user.preferred_language
        messages.success(self.request, _("Job posted."))
        return super().form_valid(form)  # saves the job and redirects


class MyJobsView(EmployerRequiredMixin, ListView):
    """The employer's own jobs in every status, soonest first (spec R14, D5)."""

    template_name = "jobs/my_jobs.html"
    context_object_name = "jobs"

    @override
    def get_queryset(self):
        """Only the logged-in employer's jobs."""
        return self.request.user.jobs.order_by("date", "start_time")


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
        jobs = Job.objects.open().upcoming().order_by("date", "start_time")
        return self.filter_form.filter(jobs)

    @override
    def get_context_data(self, **kwargs):
        """Add the filter form to what ListView gives the template (jobs, page_obj, ...)."""
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context

"""URLs of the job pages, mounted under /jobs/ (#16)."""

from django.urls import path

from . import views

urlpatterns = [
    path("new/", views.JobCreateView.as_view(), name="job_create"),
    path("mine/", views.MyJobsView.as_view(), name="my_jobs"),
    # <int:pk>: only digits reach the view; get_object() finds the job by this id.
    path("<int:pk>/edit/", views.JobEditView.as_view(), name="job_edit"),
    path("<int:pk>/cancel/", views.JobCancelView.as_view(), name="job_cancel"),
    # Photos (#64): add to a job (pk = the job), delete one photo (pk = the photo).
    path("<int:pk>/photos/", views.JobPhotoAddView.as_view(), name="job_photo_add"),
    path(
        "photos/<int:pk>/delete/",
        views.JobPhotoDeleteView.as_view(),
        name="job_photo_delete",
    ),
]

"""URLs of the reviews app, under /applications/ (#38)."""

from django.urls import path

from . import views

urlpatterns = [
    # pk = the application: a review is about one accepted application (reviews.md D4).
    path("<int:pk>/review/", views.ReviewCreateView.as_view(), name="review_create"),
]

"""URLs of the chat app, under /chat/ (#35)."""

from django.urls import path

from . import views

urlpatterns = [
    # pk = the application: one chat per accepted application (chat.md R4).
    path("<int:pk>/", views.ChatView.as_view(), name="chat"),
]

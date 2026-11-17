"""URLs of the chat app, under /chat/ (#35)."""

from django.urls import path

from . import views

urlpatterns = [
    # All the user's chats, the target of the unread badge (chat.md R24, D16).
    path("", views.ChatListView.as_view(), name="chat_list"),
    # pk = the application: one chat per accepted application (chat.md R4).
    path("<int:pk>/", views.ChatView.as_view(), name="chat"),
]

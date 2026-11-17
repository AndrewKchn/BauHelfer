"""The unread count for the navigation of every page (#35, docs/specs/chat.md R22, D18).

A context processor is a function Django calls for every template rendered with a request;
what it returns is added to that template's context. Listed in TEMPLATES in
config/settings/base.py.
"""

from accounts.models import User

from .models import unread_count


def unread_messages(request):
    """`unread_messages`: the count for a logged-in worker or employer, 0 for anyone else.

    A guest or a user without a role has no chats: 0 without asking the database.
    """
    user = request.user
    if user.is_authenticated and user.role in (User.Role.WORKER, User.Role.EMPLOYER):
        return {"unread_messages": unread_count(user)}
    return {"unread_messages": 0}

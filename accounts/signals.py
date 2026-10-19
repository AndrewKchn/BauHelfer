"""Functions Django calls on auth events; connected in AccountsConfig.ready() (#124)."""

import logging

from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver

from .models import User

logger = logging.getLogger(__name__)


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request=None, **kwargs):
    """Log a wrong email or password, on our login page and on /admin/ alike.

    Django sends this from authenticate() with what was typed, the password already
    replaced by stars. The email stays out of the log: only the user id, if it exists.
    """
    email = credentials.get("username") or credentials.get(User.USERNAME_FIELD)
    try:
        # The same lookup login uses, so ANNA@example.com is Anna too.
        user = User.objects.get_by_natural_key(email)
    except User.DoesNotExist:
        logger.warning("Failed login: unknown account")
    else:
        logger.warning("Failed login: user_id=%s", user.pk)

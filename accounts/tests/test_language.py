"""Unit tests: the language settings and UserLanguageMiddleware (#29).

docs/specs/i18n.md AC1, AC2 and R3: which languages exist, where the two language
middlewares sit in the chain, and that a logged-in user's profile language wins.
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import translation

pytestmark = pytest.mark.story(29)

User = get_user_model()


def test_languages_are_the_seven_of_the_profile():
    """The site offers exactly the 7 languages a user can store in the profile.

    1. Read LANGUAGES from the settings
    2. Expect: the same codes and names, in the same order, as User.Language
    """
    assert list(settings.LANGUAGES) == list(User.Language.choices)


def test_default_language_is_english():
    """Without any other hint the site is in English (D5).

    1. Read LANGUAGE_CODE
    2. Expect: "en", one of the 7 languages
    """
    assert settings.LANGUAGE_CODE == "en"
    assert settings.LANGUAGE_CODE in dict(settings.LANGUAGES)


def test_translations_are_read_from_the_locale_folder():
    """Django finds our .mo files in locale/ at the project root.

    1. Read LOCALE_PATHS
    2. Expect: BASE_DIR / "locale"
    """
    assert list(settings.LOCALE_PATHS) == [settings.BASE_DIR / "locale"]


def test_locale_middleware_sits_between_sessions_and_common():
    """LocaleMiddleware comes after the session and before CommonMiddleware (R2).

    1. Read MIDDLEWARE
    2. Expect: SessionMiddleware < LocaleMiddleware < CommonMiddleware
    """
    chain = settings.MIDDLEWARE
    locale = chain.index("django.middleware.locale.LocaleMiddleware")

    assert chain.index("django.contrib.sessions.middleware.SessionMiddleware") < locale
    assert locale < chain.index("django.middleware.common.CommonMiddleware")


def test_user_language_middleware_comes_after_authentication():
    """UserLanguageMiddleware needs request.user, so it runs after authentication (R3).

    1. Read MIDDLEWARE
    2. Expect: AuthenticationMiddleware < UserLanguageMiddleware
    """
    chain = settings.MIDDLEWARE

    assert chain.index(
        "django.contrib.auth.middleware.AuthenticationMiddleware"
    ) < chain.index("accounts.middleware.UserLanguageMiddleware")


def run_middleware(user):
    """Pass a request for `user` through UserLanguageMiddleware with English active.

    Returns the language active inside the view and request.LANGUAGE_CODE.
    """
    # Imported here, so each test fails on its own while the class does not exist yet.
    from accounts.middleware import UserLanguageMiddleware

    request = RequestFactory().get("/")
    request.user = user
    request.LANGUAGE_CODE = "en"  # what LocaleMiddleware chose before us
    seen = {}

    def view(request):
        seen["active"] = translation.get_language()
        seen["request"] = request.LANGUAGE_CODE

    with translation.override("en"):
        UserLanguageMiddleware(view)(request)
    return seen


@pytest.mark.django_db
def test_middleware_switches_to_the_profile_language():
    """For a logged-in user the language from the profile is active (D3).

    1. A user with preferred_language "ru"; English is active
    2. Pass a request through UserLanguageMiddleware
    3. Expect: inside the view Russian is active, request.LANGUAGE_CODE is "ru"
    """
    user = User.objects.create_user(
        email="olga@example.com", password="x", preferred_language="ru"
    )

    assert run_middleware(user) == {"active": "ru", "request": "ru"}


def test_middleware_leaves_guests_to_the_cookie():
    """A guest keeps the language LocaleMiddleware chose.

    1. A guest; English is active
    2. Pass a request through UserLanguageMiddleware
    3. Expect: English is still active
    """
    assert run_middleware(AnonymousUser()) == {"active": "en", "request": "en"}

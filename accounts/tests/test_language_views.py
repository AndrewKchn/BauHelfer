"""Integration tests: the language switcher through the Django test client (#29).

Each test goes through the whole stack: middleware, URL, view, template and database.
Acceptance criteria AC3-AC10 from docs/specs/i18n.md.
"""

import re

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from pytest_django.asserts import assertRedirects

pytestmark = [pytest.mark.django_db, pytest.mark.story(29)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"
COOKIE = settings.LANGUAGE_COOKIE_NAME  # "django_language"


def switch(client, language, next_url="/"):
    """Send the switcher form: choose `language`, come back to `next_url`."""
    return client.post(
        reverse("set_language"), {"language": language, "next": next_url}
    )


def page_language(response):
    """The language the page was rendered in: <html lang="…">."""
    match = re.search(r'<html lang="([^"]+)"', response.text)
    assert match, response.text[:200]
    return match.group(1)


@pytest.fixture
def worker():
    """A logged-in-able worker who finished onboarding, English in the profile."""
    return User.objects.create_user(
        email="ivan@example.com", password=PASSWORD, role="worker"
    )


# AC3, AC4: guests


def test_guest_switches_to_russian(client):
    """A guest chooses Russian and sees the next page in Russian.

    1. As a guest, choose "ru" in the switcher, coming from the home page
    2. Expect: the cookie django_language=ru, redirect back to the home page
    3. Open the home page
    4. Expect: <html lang="ru"> and the switcher's label in Russian
    """
    response = switch(client, "ru")

    assertRedirects(response, "/")
    assert response.cookies[COOKIE].value == "ru"

    page = client.get("/")
    assert page_language(page) == "ru"
    assert 'aria-label="Сменить язык"' in page.text


def test_guest_gets_the_browser_language(client):
    """Without a cookie the browser's language is used, if we have it.

    1. As a guest without a cookie, open the home page with Accept-Language: pl
    2. Expect: <html lang="pl">
    """
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="pl")

    assert page_language(response) == "pl"


def test_guest_with_another_browser_language_gets_english(client):
    """A browser language we do not offer falls back to English (D5).

    1. As a guest without a cookie, open the home page with Accept-Language: ja
    2. Expect: <html lang="en">
    """
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="ja")

    assert page_language(response) == "en"


# AC5, AC6: logged-in users


def test_logged_in_switch_is_saved_in_the_profile(client, worker):
    """A logged-in user's choice is stored in preferred_language.

    1. Log in as a worker with English in the profile
    2. Choose "uk" in the switcher
    3. Expect: preferred_language is "uk" in the database, the next page is Ukrainian
    """
    client.force_login(worker)

    switch(client, "uk")

    worker.refresh_from_db()
    assert worker.preferred_language == "uk"
    assert page_language(client.get("/")) == "uk"


def test_profile_language_wins_over_the_cookie(client, worker):
    """On a phone whose cookie says German, the user still sees their own language (D3).

    1. A worker with preferred_language "ru"; the browser has the cookie "de"
    2. Log in and open the home page
    3. Expect: <html lang="ru">
    """
    worker.preferred_language = "ru"
    worker.save()
    client.cookies[COOKIE] = "de"
    client.force_login(worker)

    response = client.get("/")

    assert page_language(response) == "ru"


# AC7: what the switcher refuses


def test_unknown_language_changes_nothing(client, worker):
    """A code that is not one of the 7 is ignored.

    1. Log in as a worker with English in the profile
    2. Choose "xx"
    3. Expect: no language cookie, the profile still says "en"
    """
    client.force_login(worker)

    response = switch(client, "xx")

    assert COOKIE not in response.cookies
    worker.refresh_from_db()
    assert worker.preferred_language == "en"


def test_next_to_another_site_goes_home(client):
    """The switcher never sends the user to another site (open redirect).

    1. As a guest, choose "de" with next=https://evil.example/
    2. Expect: redirect to the home page
    """
    response = switch(client, "de", next_url="https://evil.example/")

    assertRedirects(response, "/", fetch_redirect_response=False)


def test_switching_needs_a_post(client):
    """Opening the switcher's address does nothing: it changes state, so POST only.

    1. GET the set_language URL
    2. Expect: 405
    """
    response = client.get(reverse("set_language"))

    assert response.status_code == 405


# AC8: onboarding


def test_user_without_role_can_switch_the_language(client):
    """A user who has not chosen a role yet can still change the language (R5).

    1. Log in as a user without a role
    2. Choose "tr", coming from the role page
    3. Expect: back on the role page, preferred_language is "tr"
    """
    newbie = User.objects.create_user(email="newbie@example.com", password=PASSWORD)
    client.force_login(newbie)

    response = switch(client, "tr", next_url=reverse("role_select"))

    assertRedirects(response, reverse("role_select"))
    newbie.refresh_from_db()
    assert newbie.preferred_language == "tr"


# AC9: signup


def test_signup_saves_the_current_language(client):
    """A guest who chose Romanian keeps it after signing up (D9).

    1. As a guest, choose "ro"
    2. Sign up
    3. Expect: the new user's preferred_language is "ro"
    """
    switch(client, "ro")

    client.post(
        reverse("register"),
        {"email": "radu@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )

    assert User.objects.get(email="radu@example.com").preferred_language == "ro"


# AC10: the switcher in the header


def switcher(response):
    """The switcher's form in the page."""
    match = re.search(
        rf'<form[^>]*action="{reverse("set_language")}".*?</form>',
        response.text,
        re.DOTALL,
    )
    assert match, "no language switcher in the page"
    return match.group(0)


@pytest.mark.parametrize("logged_in", [False, True], ids=["guest", "logged_in"])
def test_header_has_the_switcher(client, worker, logged_in):
    """Every visitor finds the switcher in the header, with all 7 languages.

    1. Open the home page as a guest / a logged-in worker
    2. Expect: the switcher shows "EN"; one button per language with its own name; English
       is marked as the current one
    """
    if logged_in:
        client.force_login(worker)

    form = switcher(client.get("/"))

    assert ">EN<" in form
    for code, name in settings.LANGUAGES:
        assert f'value="{code}"' in form
        assert name in form
    buttons = re.findall(r"<button[^>]*>", form)
    current = [b for b in buttons if 'aria-current="true"' in b]
    assert len(current) == 1
    assert 'value="en"' in current[0]


def test_switcher_comes_back_to_the_same_page(client):
    """After switching the user is on the page they were on, with its filters.

    1. Open the job list with a filter in the query string
    2. Expect: the switcher's next is the path with the query string
    """
    form = switcher(client.get("/?days=7"))

    assert 'name="next" value="/?days=7"' in form

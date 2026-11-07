"""Integration tests: the job list renders in each of the 7 languages (#30).

Each test goes through the whole stack: middleware, URL, view, template and the compiled
translations in locale/. Spec: docs/specs/translations.md, acceptance criterion AC6.
The expected title is read from the same catalog Django uses, so the test checks that the
page is rendered in that language, not the wording of a translation.
"""

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from pytest_django.asserts import assertContains

pytestmark = [pytest.mark.django_db, pytest.mark.story(30)]

ENGLISH_TITLE = "Jobs in Munich"


@pytest.mark.parametrize("code", [code for code, _name in settings.LANGUAGES])
def test_job_list_is_in_the_chosen_language(client, code):
    """The job list page is marked and titled in the language chosen in the switcher.

    1. As a guest with the language cookie set to the language, open the job list
    2. Expect: <html lang="<code>"> and the title in that language, which differs from
       the English one for every language but English
    """
    with translation.override(code):
        title = translation.gettext(ENGLISH_TITLE)
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = code

    response = client.get(reverse("home"))

    assertContains(response, f'<html lang="{code}">')
    assertContains(response, f'<h1 class="text-2xl font-bold">{title}</h1>')
    assert (title == ENGLISH_TITLE) == (code == "en"), title

"""Unit tests: production translates with Claude, everything else with the fake translator (#31).

Spec: docs/specs/ai-translation.md, iteration 2 (R9, D11), acceptance criterion AC12. The
production settings are loaded with a made-up key; nothing here reaches the network.
"""

import re

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# media_env is the autouse fixture of test_deploy.py; imported, pytest uses it here too, so
# every test starts with the variables set, as on Render.
from tests.test_deploy import (
    TRANSLATION_ENV,
    load_production_settings,
    media_env,  # noqa: F401
)

pytestmark = [pytest.mark.story(31)]


def test_production_translates_with_claude():
    """Production uses the Claude translator with the key from ANTHROPIC_API_KEY (AC12).

    1. Set the variables as on Render; load the production settings
    2. Expect: TRANSLATION_BACKEND is ClaudeBackend
    3. Expect: ANTHROPIC_API_KEY is the value from the environment
    """
    production = load_production_settings()

    assert (
        production.TRANSLATION_BACKEND == "translations.backends.claude.ClaudeBackend"
    )
    assert production.ANTHROPIC_API_KEY == TRANSLATION_ENV["ANTHROPIC_API_KEY"]


def test_production_does_not_start_without_the_key(monkeypatch):
    """Without ANTHROPIC_API_KEY production stops at start (D11).

    Otherwise the site would run and every translation would fail, seen only in the logs.

    1. Remove ANTHROPIC_API_KEY
    2. Load the production settings
    3. Expect: ImproperlyConfigured naming the variable
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    with pytest.raises(ImproperlyConfigured, match="ANTHROPIC_API_KEY"):
        load_production_settings()


def test_render_asks_for_the_key():
    """render.yaml lists ANTHROPIC_API_KEY; Render asks for its value (R9).

    1. Read render.yaml
    2. Expect: the variable followed by "sync: false" (set in the dashboard, never in git)
    """
    text = (settings.BASE_DIR / "render.yaml").read_text()

    assert re.search(r"key: ANTHROPIC_API_KEY\s+sync: false", text)


def test_env_example_documents_the_key():
    """.env.example has ANTHROPIC_API_KEY with an empty value (R9).

    1. Read .env.example
    2. Expect: a line "ANTHROPIC_API_KEY=" with nothing after it: locally the fake
       translator needs no key, and no key is ever written into the repo
    """
    text = (settings.BASE_DIR / ".env.example").read_text()

    assert re.search(r"^ANTHROPIC_API_KEY=$", text, re.MULTILINE)


def test_local_settings_use_the_fake_translator():
    """Locally runserver translates with the fake translator, even with a key in .env.

    1. Read TRANSLATION_BACKEND of the local settings module
    2. Expect: FakeBackend; a real call only through the manual check (R11)
    """
    from config.settings import local

    assert local.TRANSLATION_BACKEND == "translations.backends.fake.FakeBackend"

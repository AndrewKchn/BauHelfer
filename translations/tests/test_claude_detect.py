"""Unit tests: the Claude translator finds the language of a text (#32).

Spec: docs/specs/job-translation.md, iteration 1 (R3, D2, D3), acceptance criterion AC2.
The `anthropic` client is replaced by the FakeClient of test_claude_backend.py: it records
the request and answers like the API, so no test reaches the network or costs money.
"""

import anthropic
import pytest

from translations.backends import TranslationError
from translations.backends.claude import ClaudeBackend

from .test_claude_backend import (
    API_REQUEST,
    FakeClient,
    RaisingClient,
    answer,
    api_status_error,
)

pytestmark = [pytest.mark.story(32)]

JOB_TEXT = "Нужны 2 человека на демонтаж, звонить Ивану +49 151 2345678"


def detect_with(client, text=JOB_TEXT):
    """Detect the language of `text` with ClaudeBackend on `client`; answer and request."""
    result = ClaudeBackend(client=client).detect_language(text)
    [request] = client.requests
    return result, request


def test_request_is_short_haiku_without_thinking():
    """The request names the translator's model, turns thinking off, allows 10 tokens.

    1. Detect the language of the job text
    2. Expect: model "claude-haiku-5-5", thinking {"type": "disabled"}, max_tokens 10
    """
    _, request = detect_with(FakeClient(answer("ru")))

    assert request["model"] == "claude-haiku-5-5"
    assert request["thinking"] == {"type": "disabled"}
    assert request["max_tokens"] == 10


def test_prompt_lists_the_codes_and_the_text_is_data():
    """The system prompt asks for one of our codes or "other"; the text is inside <text>.

    1. Detect the language of the job text
    2. Expect: the system prompt names the 7 codes, "other" and the <text> tags
    3. Expect: the user message is the job text inside <text>…</text>, unchanged
    """
    _, request = detect_with(FakeClient(answer("ru")))

    for code in ["de", "en", "ru", "uk", "pl", "ro", "tr", "other", "<text>"]:
        assert code in request["system"]
    assert request["messages"] == [
        {"role": "user", "content": f"<text>{JOB_TEXT}</text>"}
    ]


@pytest.mark.parametrize(
    ("reply", "code"), [("ru", "ru"), (" de\n", "de"), ("other", "")]
)
def test_answer_becomes_a_code(reply, code):
    """A code comes back stripped; "other" becomes "", a language not among our 7 (D3).

    1. Claude answers "ru", " de" with whitespace, or "other"
    2. Detect the language of the job text
    3. Expect: "ru", "de" or ""
    """
    result, _ = detect_with(FakeClient(answer(reply)))

    assert result == code


@pytest.mark.parametrize("reply", ["Russian", "ar", "The text is in Russian.", ""])
def test_unexpected_answer_raises(reply):
    """An answer that is not one of our codes or "other" is an error, never saved.

    1. Claude answers a language name, a code not ours, a sentence or nothing
    2. Detect the language of the job text
    3. Expect: TranslationError
    """
    with pytest.raises(TranslationError):
        detect_with(FakeClient(answer(reply)))


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_unfinished_answer_raises(stop_reason):
    """An answer cut off or declined is an error, as for a translation (ai-translation D14).

    1. Claude answers "ru" but stops with max_tokens or refusal
    2. Detect the language of the job text
    3. Expect: TranslationError
    """
    with pytest.raises(TranslationError):
        detect_with(FakeClient(answer("ru", stop_reason=stop_reason)))


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIConnectionError(request=API_REQUEST),
        api_status_error(anthropic.RateLimitError, 429),
    ],
    ids=["network", "rate-limit"],
)
def test_api_errors_become_translation_error(error):
    """An API error is raised as TranslationError, so the service keeps the language.

    1. The client raises an API error: network or 429
    2. Detect the language of the job text
    3. Expect: TranslationError
    """
    with pytest.raises(TranslationError):
        ClaudeBackend(client=RaisingClient(error)).detect_language(JOB_TEXT)


def test_each_call_is_logged_without_the_text(caplog):
    """Every call leaves one INFO line with the code, the hash and tokens, not the text.

    1. Claude answers "other"
    2. Detect the language of the job text
    3. Expect: "Language detected: lang=other hash=<12> input_tokens=120
       output_tokens=45", without the text or its phone number
    """
    caplog.set_level("INFO", logger="translations")

    detect_with(FakeClient(answer("other")))

    [record] = [r for r in caplog.records if r.name.startswith("translations")]
    message = record.getMessage()
    assert message.startswith("Language detected: lang=other hash=")
    assert message.endswith(" input_tokens=120 output_tokens=45")
    assert "+49 151" not in caplog.text
    assert "демонтаж" not in caplog.text

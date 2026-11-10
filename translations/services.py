"""Translate user texts once per language and keep the result (#31, #34).

Views of #32, #33 and #36 call translate() to show a job or message in the reader's
language, and forget() when that job or message is deleted or edited. The job form calls
detect_language() to know which language a description is in (#32).
Specs: docs/specs/ai-translation.md, docs/specs/job-translation.md.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from .backends import TranslationError
from .models import Translation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Translated:
    """What translate() gives back: the text to show and whether it is a translation.

    `ok` is false when `text` is the original, because translating failed or a limit was
    reached (D15): a page must not label it "translated".
    """

    text: str
    ok: bool


def source_hash(text):
    """The SHA-256 of `text` in hex: how the cache finds a text without storing it (D6)."""
    return hashlib.sha256(text.encode()).hexdigest()


def translate(text, target_lang):
    """`text` in the language `target_lang`, from the cache or else from the translator.

    Empty text comes back as it is (D7). `target_lang` must be one of the site's
    languages, otherwise ValueError (D8). The translator is the class named in
    TRANSLATION_BACKEND (D5); it is asked only when the cache has no row yet. A text too
    long, the daily limit reached or the translator failing give the original with
    `ok` false, never an error (#34: D15-D17, D20).
    """
    if target_lang not in dict(settings.LANGUAGES):
        raise ValueError(f"Unknown target language: {target_lang!r}")
    if not text.strip():
        return Translated(text, ok=True)

    key = source_hash(text)
    cached = Translation.objects.filter(
        source_hash=key, target_language=target_lang
    ).first()
    if cached:
        return Translated(cached.text, ok=True)

    # The limits come after the cache: what is saved costs nothing to show again.
    if len(text) > settings.TRANSLATION_MAX_LENGTH:
        return _original(text, target_lang, key, "skipped: reason=too_long")
    if _translations_today() >= settings.TRANSLATION_DAILY_LIMIT:
        return _original(text, target_lang, key, "skipped: reason=daily_limit")

    translator = import_string(settings.TRANSLATION_BACKEND)()
    try:
        translated = translator.translate(text, target_lang)
    except TranslationError as error:
        # Only the class name: the message of an API error can quote the request (D20).
        error_name = f" error={type(error).__name__}"
        return _original(text, target_lang, key, "failed:", error_name)
    # get_or_create: if another request saved the same row meanwhile, keep that one.
    row, _ = Translation.objects.get_or_create(
        source_hash=key, target_language=target_lang, defaults={"text": translated}
    )
    return Translated(row.text, ok=True)


def _translations_today():
    """How many translations the site saved in the last 24 hours (D17)."""
    since = timezone.now() - timedelta(hours=24)
    return Translation.objects.filter(created_at__gte=since).count()


def _original(text, target_lang, key, event, tail=""):
    """Log why `text` is not translated, without the text; return it as the original.

    The line: "Translation <event> lang=<code> hash=<first 12 characters><tail>".
    """
    logger.warning(
        "Translation %s lang=%s hash=%s%s", event, target_lang, key[:12], tail
    )
    return Translated(text, ok=False)


def detect_language(text):
    """The language `text` is written in: one of our 7 codes, "" for another, or None.

    None means "cannot tell": empty text, a text too long to send (D16), or a translator
    that failed. The caller then keeps the language it had (job-translation.md R2, D11),
    so saving a job never depends on the API. Nothing is cached: a job asks once per save
    of a new or changed description.
    """
    if not text.strip() or len(text) > settings.TRANSLATION_MAX_LENGTH:
        return None
    translator = import_string(settings.TRANSLATION_BACKEND)()
    try:
        return translator.detect_language(text)
    except TranslationError as error:
        # As in translate(): the class name only, never the text (D20).
        logger.warning(
            "Language detection failed: hash=%s error=%s",
            source_hash(text)[:12],
            type(error).__name__,
        )
        return None


def forget(text):
    """Delete the translations of `text` in every language (D3)."""
    Translation.objects.filter(source_hash=source_hash(text)).delete()

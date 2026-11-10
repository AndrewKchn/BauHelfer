"""Translate user texts once per language and keep the result (#31).

Views of #32, #33 and #36 call translate() to show a job or message in the reader's
language, and forget() when that job or message is deleted or edited.
Spec: docs/specs/ai-translation.md.
"""

import hashlib

from django.conf import settings
from django.utils.module_loading import import_string

from .models import Translation


def source_hash(text):
    """The SHA-256 of `text` in hex: how the cache finds a text without storing it (D6)."""
    return hashlib.sha256(text.encode()).hexdigest()


def translate(text, target_lang):
    """`text` in the language `target_lang`, from the cache or else from the translator.

    Empty text comes back as it is (D7). `target_lang` must be one of the site's
    languages, otherwise ValueError (D8). The translator is the class named in
    TRANSLATION_BACKEND (D5); it is asked only when the cache has no row yet.
    """
    if target_lang not in dict(settings.LANGUAGES):
        raise ValueError(f"Unknown target language: {target_lang!r}")
    if not text.strip():
        return text

    key = source_hash(text)
    cached = Translation.objects.filter(
        source_hash=key, target_language=target_lang
    ).first()
    if cached:
        return cached.text

    translator = import_string(settings.TRANSLATION_BACKEND)()
    translated = translator.translate(text, target_lang)
    # get_or_create: if another request saved the same row meanwhile, keep that one.
    row, _ = Translation.objects.get_or_create(
        source_hash=key, target_language=target_lang, defaults={"text": translated}
    )
    return row.text


def forget(text):
    """Delete the translations of `text` in every language (D3)."""
    Translation.objects.filter(source_hash=source_hash(text)).delete()

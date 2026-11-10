"""Translators for TRANSLATION_BACKEND.

Each has translate(text, target_lang) -> str and, since #32, detect_language(text) ->
one of our 7 codes, "" for another language, or None when it cannot tell.
"""


class TranslationError(Exception):
    """A translator could not translate: the service then shows the original (#34, D20).

    Every translator raises this one class for its own failures (Claude: an API error, an
    answer cut off or declined), so services.py needs to know no translator's library.
    """

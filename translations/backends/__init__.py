"""Translators for TRANSLATION_BACKEND: each has translate(text, target_lang) -> str."""


class TranslationError(Exception):
    """A translator could not translate: the service then shows the original (#34, D20).

    Every translator raises this one class for its own failures (Claude: an API error, an
    answer cut off or declined), so services.py needs to know no translator's library.
    """

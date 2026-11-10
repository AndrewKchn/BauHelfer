"""What the job page shows of a description: the original or a translation, and its label.

Ticket #32, docs/specs/job-translation.md (R7, R9, D3, D7-D10). Kept out of the view, so
the rule can be tested without a request; the view only calls description_for().
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

from translations.services import translate

# One whole sentence per source language: a language name cannot be put into one sentence,
# German says "aus dem Russischen", Russian "с немецкого" (D9). "" is a language not among
# our 7 (D3).
TRANSLATED_FROM = {
    "de": _("Translated from German by AI"),
    "en": _("Translated from English by AI"),
    "ru": _("Translated from Russian by AI"),
    "uk": _("Translated from Ukrainian by AI"),
    "pl": _("Translated from Polish by AI"),
    "ro": _("Translated from Romanian by AI"),
    "tr": _("Translated from Turkish by AI"),
    "": _("Translated by AI"),
}


@dataclass(frozen=True)
class Description:
    """The text to show and why it is that one.

    `state`: "translated"; "own" (the owner reads their text, D7); "same" (written in the
    reader's language, D8); "unavailable" (the translation failed, the original, D10);
    "original" (the reader asked for the original with "Show original", R12).
    `from_language`: the job's `original_language`, "" when unknown.
    """

    text: str
    state: str
    from_language: str

    @property
    def label(self):
        """The line under a translated text, e.g. "Translated from German by AI"."""
        return TRANSLATED_FROM[self.from_language]


def description_for(job, reader_lang, *, is_owner, show_original=False):
    """The description of `job` as a reader in `reader_lang` should see it (R7, R12).

    `show_original`: the page was asked for with ?original=1. It matters only where there
    would be a translation, and then nothing is translated.
    """
    original = job.description
    source = job.original_language
    if is_owner:
        return Description(original, "own", source)
    if source == reader_lang:
        return Description(original, "same", source)
    if show_original:
        return Description(original, "original", source)
    translated = translate(original, reader_lang)
    if translated.ok:
        return Description(translated.text, "translated", source)
    return Description(original, "unavailable", source)

"""What a reader sees of a user's text: the original or a translation, and its label.

Tickets #32 and #33: docs/specs/job-translation.md (R7, R9, D3, D7-D10),
docs/specs/application-translation.md (R1-R3, D5, D12). shown_text() is the rule for any
text: it gets plain values, no model, so the job description, the application messages and
the chat (#36) share it. Each kind of text has a small wrapper that takes the values out of
its model, such as description_for(). The translator (translations.services) only
translates; who sees what is decided here, and the template only draws the result.
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
class ShownText:
    """The text to show and why it is that one: the rule's answer, drawn by the template.

    `state`: "translated"; "own" (the author reads their text, D7); "same" (written in the
    reader's language, D8); "unavailable" (the translation failed, the original, D10);
    "original" (the reader asked for the original with "Show original", R12).
    `from_language`: the language the text was written in, "" when unknown.
    Frozen: once the rule has decided, nobody changes the answer.
    """

    text: str
    state: str
    from_language: str

    @property
    def label(self):
        """The line under a translated text, e.g. "Translated from German by AI"."""
        return TRANSLATED_FROM[self.from_language]


def shown_text(
    text, from_language, reader_lang, *, is_author, translated, show_original=False
):
    """`text`, written in `from_language`, as a reader in `reader_lang` should see it.

    `is_author`: the reader wrote it. `show_original`: the reader asked for the original.
    `translated`: a function giving the `Translated` of `text` in `reader_lang`; called
    only when a translation is shown, so the other states cost no translator call.
    """
    if is_author:
        return ShownText(text, "own", from_language)
    if from_language == reader_lang:
        return ShownText(text, "same", from_language)
    if show_original:
        return ShownText(text, "original", from_language)
    result = translated()
    if result.ok:
        return ShownText(result.text, "translated", from_language)
    return ShownText(text, "unavailable", from_language)


def description_for(job, reader_lang, *, is_owner, show_original=False):
    """The description of `job` as a reader in `reader_lang` should see it (#32, R7, R12).

    `is_owner`: the reader is the job's employer, the author of the description.
    """
    return shown_text(
        job.description,
        job.original_language,
        reader_lang,
        is_author=is_owner,
        translated=lambda: translate(job.description, reader_lang),
        show_original=show_original,
    )

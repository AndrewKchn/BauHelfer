"""Stands in for ClaudeBackend on runserver and in tests (#31 D5; named in #32 D14).

TRANSLATION_BACKEND in base.py points here, as EMAIL_BACKEND points to the console:
the site works without an Anthropic key, and nothing leaves the computer.
"""


class FakeClaudeBackend:
    """Does not translate: marks the text "[<lang>] <text>". No key, no network, no cost."""

    def translate(self, text, target_lang):
        """Return `text` marked with the target language, e.g. "[pl] Abriss ab Montag"."""
        return f"[{target_lang}] {text}"

    def detect_language(self, text):
        """Cannot tell (#32, job-translation.md R4): a job keeps its employer's language.

        Returns None, as the service does when a translator fails.
        """

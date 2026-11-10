"""A translator that only marks the text, for runserver and tests (#31, D5)."""


class FakeBackend:
    """Answers "[<lang>] <text>": no key, no network, no cost, like the console email."""

    def translate(self, text, target_lang):
        """Return `text` marked with the target language, e.g. "[pl] Abriss ab Montag"."""
        return f"[{target_lang}] {text}"

    def detect_language(self, text):
        """Cannot tell (#32, job-translation.md R4): a job keeps its employer's language.

        Returns None, as the service does when a translator fails.
        """

"""The translation cache: one row per source text and target language (#31)."""

from django.conf import settings
from django.db import models


class Translation(models.Model):
    """A user text translated into one language, found by the text's SHA-256.

    The source text itself is not stored, only its hash (ai-translation.md D6). The
    translation still contains what the author wrote, names and phone numbers too, so
    services.forget() deletes the rows of a text when its job or message goes (D3).
    """

    source_hash = models.CharField(max_length=64)  # SHA-256 in hex
    target_language = models.CharField(max_length=7, choices=settings.LANGUAGES)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            # One row per text and language: two requests that translate the same text at
            # the same instant cannot both save (services.translate keeps the first).
            models.UniqueConstraint(
                fields=["source_hash", "target_language"],
                name="one_translation_per_text_and_language",
            ),
        )

    def __str__(self):
        return f"{self.source_hash[:12]} → {self.target_language}"

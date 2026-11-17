"""The form under the chat (#35, docs/specs/chat.md R6)."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Message


class MessageForm(forms.ModelForm):
    """Only the text: the view sets the application and the sender from the URL and the
    login, so nobody can write in someone else's chat or name.

    The form field strips spaces, so "   " is empty and refused as required; max_length
    1000 comes from the model (D5).
    """

    class Meta:
        model = Message
        fields = ("text",)
        labels = {"text": _("Message")}  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "text": forms.Textarea(
                attrs={
                    "rows": 2,
                    "class": "textarea w-full",
                    "placeholder": _("Write a message…"),
                }
            )
        }

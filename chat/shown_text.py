"""Chat messages as their reader should see them: the original or a translation (#36).

docs/specs/chat-translation.md, layer 3 "wrapper" (R4, D5, D6). The rule itself is
jobs.shown_text.shown_text(), shared with the job descriptions and the application
messages; this module only takes the values out of a Message. Unlike a job page, a chat
page holds the texts of both people, so whether the reader is the author is asked for
each message.
"""

from jobs.shown_text import shown_text
from translations.services import translate_many


def chat_messages_for(messages, reader, reader_lang):
    """Give each message a `shown` (ShownText): its text as `reader` should see it.

    The messages that need a translation (the other person's, not in `reader_lang`) are
    read from the cache in one query (translate_many, D6); they were translated when sent
    (D1), so normally no Claude call happens here. Returns the messages as a list.
    """
    messages = list(messages)
    needed = [
        m.text
        for m in messages
        if m.sender_id != reader.pk and m.original_language != reader_lang
    ]
    translations = translate_many(needed, reader_lang)
    for message in messages:
        message.shown = shown_text(
            message.text,
            message.original_language,
            reader_lang,
            is_author=message.sender_id == reader.pk,
            # `text=` binds this message's text now, not the loop variable (ruff B023).
            translated=lambda text=message.text: translations[text],
        )
    return messages

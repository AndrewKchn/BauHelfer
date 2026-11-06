"""The translation checks for tests/test_translations.py (#29, docs/specs/i18n.md R9, R11).

Both run gettext's msgfmt, the program Django's compilemessages runs too, so no Python
package is needed (D11). gettext is installed with `sudo apt install gettext` locally and by
a step in CI.
"""

import gettext
import os
import re
import subprocess
import tempfile
from pathlib import Path

# msgfmt prints its counts in the language of the system; C = English, so we can read them.
ENGLISH = {**os.environ, "LC_ALL": "C"}


def statistics(po):
    """Count the translated, fuzzy and untranslated strings of the .po file `po`.

    msgfmt --statistics prints one line such as
    "1 translated message, 2 fuzzy translations, 334 untranslated messages."
    (a kind with 0 strings is left out). Obsolete #~ entries are not counted.
    """
    result = subprocess.run(
        ["msgfmt", "--statistics", "-o", os.devnull, str(po)],
        capture_output=True,
        text=True,
        check=True,  # a broken .po raises here instead of looking translated
        env=ENGLISH,
    )
    counts = {"translated": 0, "fuzzy": 0, "untranslated": 0}
    for number, kind in re.findall(
        r"(\d+) (translated|fuzzy|untranslated)", result.stderr
    ):
        counts[kind] = int(number)
    return counts


def mo_is_current(po):
    """True if the django.mo next to `po` holds exactly the translations of `po`.

    Compiles `po` again into a temporary file and compares the two catalogs, not the bytes:
    another gettext version may write different bytes for the same translations (D12).
    """
    po = Path(po)
    with tempfile.TemporaryDirectory() as folder:
        fresh = Path(folder) / "django.mo"
        subprocess.run(["msgfmt", "-o", str(fresh), str(po)], check=True, env=ENGLISH)
        return catalog(fresh) == catalog(po.with_suffix(".mo"))


def catalog(mo):
    """All translations in the .mo file `mo` as {msgid: msgstr}, read by Python's gettext."""
    with open(mo, "rb") as file:
        # _catalog is not public, but it is the plain dict the file was read into.
        return gettext.GNUTranslations(file)._catalog

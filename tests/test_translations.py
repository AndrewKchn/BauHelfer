"""Unit tests: the translation files in locale/ are complete and compiled (#29).

docs/specs/i18n.md AC11-AC13. The check itself (tests/translations.py) runs gettext's
msgfmt, so gettext must be installed: `sudo apt install gettext` locally, a step in CI.
"""

import subprocess

import pytest
from django.conf import settings

pytestmark = pytest.mark.story(29)

LOCALE = settings.BASE_DIR / "locale"
# Every site language except English: the strings in the code are English (D10).
TRANSLATED = [code for code, _name in settings.LANGUAGES if code != "en"]

HEADER = """msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

"""


@pytest.fixture
def check():
    """The module with the check, tests/translations.py.

    Imported in a fixture, so each test fails on its own while the module does not exist.
    """
    import tests.translations

    return tests.translations


def write_po(folder, entries):
    """Write a small .po file with `entries` (text after the header); return its path."""
    po = folder / "django.po"
    po.write_text(HEADER + entries, encoding="utf-8")
    return po


# AC11: the check finds untranslated and fuzzy strings


def test_untranslated_string_is_found(tmp_path, check):
    """A string with an empty translation is counted as untranslated.

    1. Write a .po with one translated and one untranslated string
    2. Expect: 1 translated, 0 fuzzy, 1 untranslated
    """
    po = write_po(
        tmp_path,
        'msgid "Log in"\nmsgstr "Войти"\n\nmsgid "Log out"\nmsgstr ""\n',
    )

    assert check.statistics(po) == {"translated": 1, "fuzzy": 0, "untranslated": 1}


def test_fuzzy_string_is_found(tmp_path, check):
    """A translation marked fuzzy (a guess by makemessages) is counted as fuzzy.

    1. Write a .po with one fuzzy translation
    2. Expect: 0 translated, 1 fuzzy, 0 untranslated
    """
    po = write_po(tmp_path, '#, fuzzy\nmsgid "Log in"\nmsgstr "Войти"\n')

    assert check.statistics(po) == {"translated": 0, "fuzzy": 1, "untranslated": 0}


def test_translated_file_has_nothing_to_report(tmp_path, check):
    """A fully translated .po, with an old obsolete entry, has no problems.

    1. Write a .po with one translated string and one obsolete (#~) entry
    2. Expect: 1 translated, 0 fuzzy, 0 untranslated
    """
    po = write_po(
        tmp_path,
        'msgid "Log in"\nmsgstr "Войти"\n\n#~ msgid "Old text"\n#~ msgstr ""\n',
    )

    assert check.statistics(po) == {"translated": 1, "fuzzy": 0, "untranslated": 0}


def test_broken_file_is_an_error(tmp_path, check):
    """A .po that msgfmt cannot read stops the check instead of counting as translated.

    1. Write a .po with one untranslated string and a line msgfmt cannot read
    2. Expect: the check raises CalledProcessError
    """
    po = write_po(tmp_path, 'msgid "Log in"\nmsgstr ""\nmsgstr "twice"\n')

    with pytest.raises(subprocess.CalledProcessError):
        check.statistics(po)


@pytest.mark.story(30)
@pytest.mark.parametrize(
    "translation", ["Привет, %(nmae)s,", "Привет,"], ids=["renamed", "dropped"]
)
def test_broken_placeholder_is_an_error(tmp_path, check, translation):
    """A translation whose placeholder differs from the English one stops the check.

    1. Write a .po whose "Hello %(name)s," is translated with a misspelt placeholder
       (KeyError in Python code) or a missing one (the name is lost)
    2. Expect: the check raises CalledProcessError
    """
    po = write_po(
        tmp_path,
        f'#, python-format\nmsgid "Hello %(name)s,"\nmsgstr "{translation}"\n',
    )

    with pytest.raises(subprocess.CalledProcessError):
        check.statistics(po)


@pytest.mark.story(30)
def test_missing_plural_form_is_an_error(tmp_path, check):
    """A plural string with fewer forms than the language has stops the check.

    1. Write a .po for a language with 4 plural forms (Russian) whose plural string has
       only 2 (Django would show English for 5-20, e.g. "16 open")
    2. Expect: the check raises CalledProcessError
    """
    po = tmp_path / "django.po"
    po.write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=4; plural=(n%10==1 && n%100!=11 ? 0 : '
        'n%10>=2 && n%10<=4 && (n%100<12 || n%100>14) ? 1 : 2);\\n"\n\n'
        '#, python-format\nmsgid "%(counter)s open"\nmsgid_plural "%(counter)s open"\n'
        'msgstr[0] "Открыто: %(counter)s"\nmsgstr[1] "Открыто: %(counter)s"\n',
        encoding="utf-8",
    )

    with pytest.raises(subprocess.CalledProcessError):
        check.statistics(po)


def test_every_language_but_english_has_a_po_file():
    """locale/ has a .po file for each of the 6 languages, and none for English (D10).

    1. List the folders in locale/
    2. Expect: exactly de, pl, ro, ru, tr, uk, each with LC_MESSAGES/django.po
    """
    folders = sorted(path.name for path in LOCALE.iterdir() if path.is_dir())

    assert folders == sorted(TRANSLATED)
    for code in TRANSLATED:
        assert (LOCALE / code / "LC_MESSAGES" / "django.po").is_file()


# AC12: our own files (i18n.md D2). Every language fully translated since #30
# (translations.md AC5, R9).


@pytest.mark.story(30)
@pytest.mark.parametrize("code", TRANSLATED)
def test_every_string_is_translated(check, code):
    """Every string of the site is translated into this language, none is fuzzy.

    1. Count the strings in locale/<code>/LC_MESSAGES/django.po
    2. Expect: no fuzzy and no untranslated string
    """
    counts = check.statistics(LOCALE / code / "LC_MESSAGES" / "django.po")

    assert counts["fuzzy"] == counts["untranslated"] == 0, counts


# AC13: the .mo files in git are compiled from the current .po files (D4)


def test_out_of_date_mo_is_found(tmp_path, check):
    """A .mo compiled before its .po was changed is reported.

    1. Write a .po, compile it to django.mo next to it
    2. Expect: the .mo is current
    3. Change a translation in the .po without compiling
    4. Expect: the .mo is no longer current
    """
    po = write_po(tmp_path, 'msgid "Log in"\nmsgstr "Войти"\n')
    compile_po(po)
    assert check.mo_is_current(po)

    write_po(tmp_path, 'msgid "Log in"\nmsgstr "Вход"\n')

    assert not check.mo_is_current(po)


@pytest.mark.parametrize("code", TRANSLATED)
def test_committed_mo_matches_its_po(check, code):
    """The .mo Django reads holds the same translations as the .po next to it.

    1. Compile locale/<code>/LC_MESSAGES/django.po again
    2. Expect: the same translations as the django.mo in git
    """
    po = LOCALE / code / "LC_MESSAGES" / "django.po"

    assert check.mo_is_current(po), "run: uv run python manage.py compilemessages"


def compile_po(po):
    """Compile `po` into django.mo next to it, as compilemessages does."""
    subprocess.run(["msgfmt", "-o", str(po.with_suffix(".mo")), str(po)], check=True)

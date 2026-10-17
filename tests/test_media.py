"""Unit tests: where uploaded files go, locally and in tests (#64).

Spec: docs/specs/job-photos.md, iteration 1 (R8, R9). Production storage comes in
iteration 4.
"""

import pytest
from django.conf import settings
from django.core.files.storage import InMemoryStorage, default_storage

pytestmark = [pytest.mark.story(64)]


def test_tests_store_files_in_memory():
    """Tests never write uploaded files to the disk.

    1. Look at Django's default storage during a test
    2. Expect: InMemoryStorage
    """
    # default_storage is a lazy wrapper; _wrapped is the real storage after first use.
    default_storage.exists("anything")

    assert isinstance(default_storage._wrapped, InMemoryStorage)


def test_local_media_folder():
    """Locally, uploads go to media/ in the project and are served under /media/.

    1. Read MEDIA_ROOT and MEDIA_URL
    2. Expect: <project>/media and "/media/"
    """
    assert settings.MEDIA_ROOT == settings.BASE_DIR / "media"
    assert settings.MEDIA_URL == "/media/"

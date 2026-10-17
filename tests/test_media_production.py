"""Unit tests: where production stores uploaded photos, Supabase Storage via S3 (#64).

Spec: docs/specs/job-photos.md, iteration 4 (R33-R37, AC36-AC40, D30, D31, D33). The
production settings are loaded with made-up values; nothing here reaches the network.
"""

import re

import pytest
from django.conf import global_settings, settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

# media_env is the autouse fixture of test_deploy.py; imported, pytest uses it here too, so
# every test starts with the six variables set, as on Render.
from tests.test_deploy import (
    MEDIA_ENV,
    load_production_settings,
    media_env,  # noqa: F401
)

pytestmark = [pytest.mark.story(64)]

SECRETS = ("MEDIA_S3_ACCESS_KEY_ID", "MEDIA_S3_SECRET_ACCESS_KEY")


def production_photo_storage():
    """The storage production's settings build for uploads, made like Django makes it."""
    default = load_production_settings().STORAGES["default"]
    return import_string(default["BACKEND"])(**default.get("OPTIONS", {}))


def test_production_stores_photos_in_the_s3_bucket():
    """Production uploads go to the S3 bucket named by the env variables (R33, AC36).

    1. Set the six storage variables
    2. Build production's default storage
    3. Expect: django-storages' S3 storage with that endpoint, region, keys and bucket
    """
    storage = production_photo_storage()

    assert type(storage).__name__ == "S3Storage"
    assert storage.endpoint_url == MEDIA_ENV["MEDIA_S3_ENDPOINT_URL"]
    assert storage.region_name == MEDIA_ENV["MEDIA_S3_REGION"]
    assert storage.access_key == MEDIA_ENV["MEDIA_S3_ACCESS_KEY_ID"]
    assert storage.secret_key == MEDIA_ENV["MEDIA_S3_SECRET_ACCESS_KEY"]
    assert storage.bucket_name == "job-photos"


def test_photo_address_is_public_and_unsigned():
    """A photo's address is a plain public URL on MEDIA_PUBLIC_URL (R35, D30).

    1. Set the six storage variables
    2. Ask production's storage for the address of job_photos/ab.jpg
    3. Expect: https://<MEDIA_PUBLIC_URL>/job_photos/ab.jpg, without a signature
    """
    url = production_photo_storage().url("job_photos/ab.jpg")

    assert url == f"https://{MEDIA_ENV['MEDIA_PUBLIC_URL']}/job_photos/ab.jpg"
    assert "Signature" not in url


@pytest.mark.parametrize(
    "written",
    [
        "https://abcdref.supabase.co/storage/v1/object/public/job-photos",
        "abcdref.supabase.co/storage/v1/object/public/job-photos/",
    ],
)
def test_public_url_may_be_written_with_https_or_a_slash(monkeypatch, written):
    """MEDIA_PUBLIC_URL works with "https://" in front or "/" at the end (R35).

    Found in the manual check: copying the address from the browser brings "https://" with
    it, and the photos would get "https://https://…" addresses: broken, with no error.

    1. Set MEDIA_PUBLIC_URL with https:// in front, or with a slash at the end
    2. Ask production's storage for the address of job_photos/ab.jpg
    3. Expect: the same address as without them
    """
    monkeypatch.setenv("MEDIA_PUBLIC_URL", written)

    url = production_photo_storage().url("job_photos/ab.jpg")

    assert url == f"https://{MEDIA_ENV['MEDIA_PUBLIC_URL']}/job_photos/ab.jpg"


def test_photos_are_never_overwritten():
    """Two uploads never replace each other in the bucket (R35).

    1. Build production's default storage
    2. Expect: file_overwrite is off
    """
    assert production_photo_storage().file_overwrite is False


@pytest.mark.parametrize("missing", list(MEDIA_ENV))
def test_production_does_not_start_without_a_storage_variable(monkeypatch, missing):
    """A missing storage variable stops the server instead of losing photos (R34, D31).

    1. Remove one of the six storage variables
    2. Load the production settings
    3. Expect: ImproperlyConfigured naming the missing variable
    """
    monkeypatch.delenv(missing)

    with pytest.raises(ImproperlyConfigured, match=missing):
        load_production_settings()


def test_env_example_lists_the_storage_variables():
    """.env.example names every storage variable, so a new clone knows them (R36, AC39).

    1. Read .env.example
    2. Expect: a line "NAME=" for each of the six variables
    """
    text = (settings.BASE_DIR / ".env.example").read_text()

    for name in MEDIA_ENV:
        assert re.search(rf"^{name}=", text, re.MULTILINE), name


def test_render_asks_for_the_storage_variables():
    """render.yaml lists the six variables; Render asks for the two secrets (R36, AC39).

    1. Read render.yaml
    2. Expect: a "key:" entry for each variable; the access key id and the secret followed
       by "sync: false" (Render asks for the value, it is never in the repo)
    """
    text = (settings.BASE_DIR / "render.yaml").read_text()

    for name in MEDIA_ENV:
        assert f"key: {name}" in text, name
    for name in SECRETS:
        assert re.search(rf"key: {name}\s+sync: false", text), name


def test_local_settings_store_uploads_on_disk():
    """Locally, uploads still go to media/ on disk (R37, AC40).

    1. Read the STORAGES of the local settings module (tests replace the live setting)
    2. Expect: Django's FileSystemStorage for uploads
    """
    from config.settings import local

    storages = getattr(local, "STORAGES", global_settings.STORAGES)

    assert (
        storages["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
    )

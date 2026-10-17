"""Integration tests: adding and deleting job photos on the edit page (#64).

Spec: docs/specs/job-photos.md, iteration 2 (R12-R18, AC12-AC22, AC24). Django test client:
middleware, URL, view, form, template, database and the (in-memory) storage.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import Client
from django.urls import reverse
from PIL import Image
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from jobs.models import Job, JobPhoto
from jobs.tests.images import camera_exif, make_upload
from jobs.tests.test_views import form_data, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(64)]

User = get_user_model()


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


@pytest.fixture
def job(employer):
    """An open job of the employer, without photos."""
    return make_job(employer)


def add_photos(job, count):
    """Give `job` `count` stored photos; returns them."""
    return [
        JobPhoto.objects.create(
            job=job, image=ContentFile(make_upload().read(), name="old.jpg")
        )
        for _ in range(count)
    ]


def edit_url(job):
    """The job's edit page, where the photo block is."""
    return reverse("job_edit", args=[job.pk])


def add_url(job):
    """Where the photo upload form posts to."""
    return reverse("job_photo_add", args=[job.pk])


def delete_url(photo):
    """Where a photo's "×" button posts to."""
    return reverse("job_photo_delete", args=[photo.pk])


# After "Publish job" (R12, R13, AC12, AC13)


def test_publish_opens_the_edit_page(employer_client):
    """Publishing a job opens its edit page at the photos, with a hint to add photos.

    1. As an employer, send a correctly filled "Post a job" form
    2. Expect: a redirect to the new job's edit page at #photos (R21) with "Job posted. You
       can add photos below." and the photo block
    """
    response = employer_client.post(reverse("job_create"), form_data(), follow=True)

    job = Job.objects.get()
    assertRedirects(response, edit_url(job) + "#photos")
    assertContains(response, "Job posted. You can add photos below.")
    assertContains(response, "Photos (0 of 5)")


def test_create_page_says_photos_come_later(employer_client, job):
    """The "Post a job" page tells that photos are added after publishing; edit does not.

    1. Open "Post a job", then the edit page of a job
    2. Expect: the hint on the first page only
    """
    hint = "You can add photos after you publish the job."

    assertContains(employer_client.get(reverse("job_create")), hint)
    assertNotContains(employer_client.get(edit_url(job)), hint)


# The photo block on the edit page (R14, R15, R18, AC14, AC15, AC24)


def test_edit_page_shows_the_photos(employer_client, job):
    """The edit page lists the job's photos with a delete button each.

    1. Give the job 2 photos
    2. Open its edit page
    3. Expect: "Photos (2 of 5)", both pictures, a delete form for each
    """
    photos = add_photos(job, 2)

    response = employer_client.get(edit_url(job))

    assertContains(response, "Photos (2 of 5)")
    for photo in photos:
        assertContains(response, photo.image.url)
        assertContains(response, f'action="{delete_url(photo)}"')


def test_edit_page_without_photos(employer_client, job):
    """A job without photos says so.

    1. Open the edit page of a job without photos
    2. Expect: "Photos (0 of 5)" and "No photos yet."
    """
    response = employer_client.get(edit_url(job))

    assertContains(response, "Photos (0 of 5)")
    assertContains(response, "No photos yet.")


def test_edit_page_has_the_upload_form(employer_client, job):
    """The upload form posts files to the add URL and takes several of them.

    1. Open the edit page of a job without photos
    2. Expect: a form posting to job_photo_add with multipart/form-data, a "multiple" file
       field, the "Add photos" button and the location hint
    """
    response = employer_client.get(edit_url(job))

    assertContains(response, f'action="{add_url(job)}"')
    assertContains(response, 'enctype="multipart/form-data"')
    assertContains(response, "multiple")
    assertContains(response, "Add photos")
    assertContains(response, "Location data is removed from photos.")


def test_full_job_has_no_upload_form(employer_client, job):
    """With 5 photos the upload form is gone and a line says why.

    1. Give the job 5 photos
    2. Open its edit page
    3. Expect: no form posting to job_photo_add; "That is the maximum of 5 photos."
    """
    add_photos(job, 5)

    response = employer_client.get(edit_url(job))

    assertNotContains(response, f'action="{add_url(job)}"')
    assertContains(response, "That is the maximum of 5 photos.")


def test_photo_block_is_the_photos_anchor(employer_client, job):
    """The photo block is the target of the #photos jump after publishing (R21, AC25).

    1. Open the edit page
    2. Expect: an element with id="photos"
    """
    response = employer_client.get(edit_url(job))

    assertContains(response, 'id="photos"')


def test_edit_page_names_its_two_parts(employer_client, job):
    """The edit page has "Job details" with "Save changes", the create page does not.

    1. Open the edit page, then "Post a job"
    2. Expect: edit has "Job details" as its heading, "Save changes", no "Edit job" heading
       and no "Save job"; create has "Publish job", not "Job details" (R20, AC26)
    """
    edit = employer_client.get(edit_url(job))
    create = employer_client.get(reverse("job_create"))

    assertContains(edit, "Job details</h1>")
    assertNotContains(edit, "Edit job</h1>")
    assertContains(edit, "Save changes")
    assertNotContains(edit, "Save job")
    assertContains(create, "Publish job")
    assertNotContains(create, "Job details")


def test_script_knows_the_edit_page(employer_client, job):
    """The job form tells the script whether it is the edit page (R22, AC27).

    The script turns "Save changes" off until a field changes; only on the edit page, and
    not when the page comes back with errors (the typed values are not saved yet).

    1. Open the edit page; post the edit form with an empty address; open "Post a job"
    2. Expect: data-edit="true" on the edit page; data-unsaved="true" on the page with
       errors; no data-edit on the create page
    """
    edit = employer_client.get(edit_url(job))
    with_errors = employer_client.post(edit_url(job), form_data(address=""))
    create = employer_client.get(reverse("job_create"))

    assertContains(edit, 'data-edit="true"')
    assertNotContains(edit, 'data-unsaved="true"')
    assertContains(with_errors, 'data-unsaved="true"')
    assertNotContains(create, 'data-edit="true"')


def test_both_buttons_have_the_same_colour(employer_client, job):
    """ "Save changes" and "Add photos" are both primary buttons (R23, AC28).

    1. Open the edit page of a job without photos
    2. Expect: two buttons with btn-primary (save and add), none with btn-secondary
    """
    response = employer_client.get(edit_url(job))

    assertContains(response, "btn btn-primary", count=2)
    assertNotContains(response, "btn-secondary")


def test_edit_page_warns_about_unsaved_changes(employer_client, job):
    """The job form page carries the script that warns before leaving with unsaved changes.

    Only the script is checked here; what it does is checked by the E2E tests of #21.

    1. Open the edit page
    2. Expect: a "beforeunload" handler in the page
    """
    response = employer_client.get(edit_url(job))

    assertContains(response, "beforeunload")


# Adding photos (R16, AC16-AC19)


def test_owner_adds_three_photos(employer_client, job):
    """Three valid photos are stored without EXIF, and the page says so.

    1. As the owner, post a JPEG with GPS EXIF, a PNG and a WebP to the add URL
    2. Expect: back on the edit page with "3 photos added."; the job has 3 photos, each a
       JPEG without EXIF
    """
    uploads = [
        make_upload(exif=camera_exif()),
        make_upload("PNG", name="b.png"),
        make_upload("WEBP", name="c.webp"),
    ]

    response = employer_client.post(add_url(job), {"photos": uploads}, follow=True)

    assertRedirects(response, edit_url(job))
    assertContains(response, "3 photos added.")
    assert job.photos.count() == 3
    for photo in job.photos.all():
        with default_storage.open(photo.image.name) as stored:
            image = Image.open(stored)
            assert image.format == "JPEG"
            assert dict(image.getexif()) == {}


def test_one_photo_added_in_singular(employer_client, job):
    """One photo is reported in the singular.

    1. As the owner, post one photo
    2. Expect: "1 photo added."
    """
    response = employer_client.post(
        add_url(job), {"photos": [make_upload()]}, follow=True
    )

    assertContains(response, "1 photo added.")


def test_one_bad_file_saves_none(employer_client, job):
    """A batch with one bad file saves nothing and names the file (D17, D18).

    1. As the owner, post two JPEGs and a GIF named plan.gif
    2. Expect: back on the edit page with "plan.gif: Upload a photo in JPEG, PNG or WebP
       format."; no photo saved
    """
    uploads = [make_upload(), make_upload("GIF", name="plan.gif"), make_upload()]

    response = employer_client.post(add_url(job), {"photos": uploads}, follow=True)

    assertRedirects(response, edit_url(job))
    assertContains(response, "plan.gif: Upload a photo in JPEG, PNG or WebP format.")
    assert not job.photos.exists()


def test_too_many_photos_saves_none(employer_client, job):
    """More photos than fit are refused with how many more fit.

    1. Give the job 4 photos
    2. As the owner, post 2 more
    3. Expect: "You can add 1 more photo."; still 4 photos
    """
    add_photos(job, 4)

    response = employer_client.post(
        add_url(job),
        {"photos": [make_upload(), make_upload(name="b.jpg")]},
        follow=True,
    )

    assertContains(response, "You can add 1 more photo.")
    assert job.photos.count() == 4


def test_no_file_chosen(employer_client, job):
    """Pressing "Add photos" without a file gives a message, nothing else.

    1. As the owner, post the add form without files
    2. Expect: back on the edit page with "Choose at least one photo."; no photo
    """
    response = employer_client.post(add_url(job), {}, follow=True)

    assertRedirects(response, edit_url(job))
    assertContains(response, "Choose at least one photo.")
    assert not job.photos.exists()


# Deleting a photo (R17, AC21)


def test_owner_deletes_a_photo(
    employer_client, job, django_capture_on_commit_callbacks
):
    """The "×" button deletes the photo and its file at once.

    1. Give the job 2 photos
    2. As the owner, post to the first photo's delete URL
    3. Expect: back on the edit page with "Photo deleted."; one photo left; the first
       photo's file is gone
    """
    first, second = add_photos(job, 2)

    with django_capture_on_commit_callbacks(execute=True):
        response = employer_client.post(delete_url(first), follow=True)

    assertRedirects(response, edit_url(job))
    assertContains(response, "Photo deleted.")
    assert list(job.photos.all()) == [second]
    assert not default_storage.exists(first.image.name)


# Who may add and delete (R16, R17, AC20, AC22)


def test_other_employer_gets_404(client, job):
    """Another employer can neither add photos to the job nor delete its photos.

    1. Give the job a photo
    2. Log in as another employer; post a photo to the add URL and to the delete URL
    3. Expect: 404 both times; the job still has exactly its one photo
    """
    (photo,) = add_photos(job, 1)
    client.force_login(make_employer("boris@example.com"))

    assert client.post(add_url(job), {"photos": [make_upload()]}).status_code == 404
    assert client.post(delete_url(photo)).status_code == 404
    assert list(job.photos.all()) == [photo]


def test_cancelled_job_gets_404(employer_client, job):
    """The photos of a job that is not open cannot be changed.

    1. Give the job a photo, then cancel the job
    2. As the owner, post to the add URL and to the delete URL
    3. Expect: 404 both times; the photo is still there
    """
    (photo,) = add_photos(job, 1)
    job.status = Job.Status.CANCELLED
    job.save()

    response = employer_client.post(add_url(job), {"photos": [make_upload()]})
    assert response.status_code == 404
    assert employer_client.post(delete_url(photo)).status_code == 404
    assert list(job.photos.all()) == [photo]


def test_guest_is_sent_to_login(client, job):
    """A guest posting to the photo URLs is sent to login.

    1. Give the job a photo
    2. Without logging in, post to the add URL and to the delete URL
    3. Expect: a redirect to the login page both times
    """
    (photo,) = add_photos(job, 1)

    for url in (add_url(job), delete_url(photo)):
        response = client.post(url)

        assertRedirects(response, f"{reverse('login')}?next={url}")


def test_worker_gets_403(client, job):
    """A worker posting to the photo URLs gets 403.

    1. Give the job a photo
    2. Log in as a worker; post to the add URL and to the delete URL
    3. Expect: 403 both times
    """
    (photo,) = add_photos(job, 1)
    client.force_login(
        User.objects.create_user(email="ivan@example.com", password="x", role="worker")
    )

    for url in (add_url(job), delete_url(photo)):
        assert client.post(url).status_code == 403, url


def test_get_is_not_allowed(employer_client, job):
    """Adding and deleting work only with POST; a link cannot do them.

    1. Give the job a photo
    2. As the owner, open the add URL and the delete URL with GET
    3. Expect: 405 both times; the photo is still there
    """
    (photo,) = add_photos(job, 1)

    assert employer_client.get(add_url(job)).status_code == 405
    assert employer_client.get(delete_url(photo)).status_code == 405
    assert job.photos.count() == 1


def test_photo_forms_need_the_csrf_token(employer, job):
    """Adding and deleting photos only work with the CSRF token of our page.

    1. Give the job a photo
    2. Log in with a client that checks CSRF like a real browser
    3. Post to the add URL and to the delete URL without the token
    4. Expect: 403 both times; the job still has exactly its one photo
    """
    (photo,) = add_photos(job, 1)
    client = Client(enforce_csrf_checks=True)
    client.force_login(employer)

    assert client.post(add_url(job), {"photos": [make_upload()]}).status_code == 403
    assert client.post(delete_url(photo)).status_code == 403
    assert list(job.photos.all()) == [photo]

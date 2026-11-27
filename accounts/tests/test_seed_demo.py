"""Integration tests: the seed_demo command fills the database with demo data (#47).

Spec: docs/specs/demo-data.md, R1-R9 and R11, acceptance criteria AC1, AC4-AC9, AC11 and AC12. The command runs
through call_command, as `manage.py seed_demo` does, on the test database. The footer line
(R10, AC10) is in tests/test_base_layout.py.
"""

import getpass
import io

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from jobs.models import Application, Job, JobPhoto
from jobs.tests.test_views import make_employer, make_job
from reviews.models import Review
from translations.models import Translation

pytestmark = [pytest.mark.django_db, pytest.mark.story(47)]

User = get_user_model()

PASSWORD = "demo-pass-47"
DEMO_DOMAIN = "@demo.example"


def seed(password=PASSWORD):
    """Run `manage.py seed_demo --password <password>`, its output thrown away."""
    call_command("seed_demo", password=password, stdout=io.StringIO())


def demo_users():
    """The accounts the command made: every address on @demo.example (D10)."""
    return User.objects.filter(email__endswith=DEMO_DOMAIN)


def counts():
    """How many demo accounts, their jobs, applications and reviews there are."""
    users = demo_users()
    return {
        "users": users.count(),
        "jobs": Job.objects.filter(employer__in=users).count(),
        "applications": Application.objects.filter(worker__in=users).count(),
        "reviews": Review.objects.filter(author__in=users).count(),
    }


# What the command creates (R3, R4; AC1)


def test_seed_creates_employers_workers_open_and_done_jobs_and_a_rating():
    """The demo site looks used: open jobs ahead, a done job, a worker with a rating.

    1. Run seed_demo
    2. Expect: demo employers and workers; open jobs, all dated after today; a done job;
       at least one demo worker whose rating counts a review (#39, visible to everyone)
    """
    seed()

    users = demo_users()
    assert users.filter(role="employer").exists()
    assert users.filter(role="worker").exists()
    open_jobs = Job.objects.filter(employer__in=users, status=Job.Status.OPEN)
    assert open_jobs.exists()
    assert not open_jobs.filter(date__lte=timezone.localdate()).exists()
    assert Job.objects.filter(employer__in=users, status=Job.Status.DONE).exists()
    ratings = [Review.objects.rating_of(w) for w in users.filter(role="worker")]
    assert any(rating.count > 0 for rating in ratings)


# Running it again (R2, D3; AC4, AC5)


def test_running_seed_twice_gives_the_same_data_as_once():
    """Running again resets the demo data instead of adding a second copy.

    1. Run seed_demo, count demo accounts, their jobs, applications and reviews
    2. Run seed_demo again
    3. Expect: the same counts, none of them zero
    """
    seed()
    first = counts()

    seed()

    assert counts() == first
    assert all(first.values())


def test_seed_leaves_every_other_account_and_its_job_alone():
    """Only @demo.example accounts are deleted: never mine, the admin or the dev users.

    1. Save a real user, a superuser, a local dev employer on @example.com with a job, and
       a user on @olddemo.example (ends with "demo.example", but not on that domain)
    2. Run seed_demo twice
    3. Expect: all four users and the job still exist
    """
    real = User.objects.create_user(email="someone@gmail.example", password="x")
    admin = User.objects.create_superuser(email="admin@bauhelfer.example", password="x")
    dev_employer = make_employer("max@example.com")
    dev_job = make_job(dev_employer)
    look_alike = User.objects.create_user(email="anna@olddemo.example", password="x")

    seed()
    seed()

    kept = User.objects.filter(
        pk__in=[real.pk, admin.pk, dev_employer.pk, look_alike.pk]
    )
    assert kept.count() == 4
    assert Job.objects.filter(pk=dev_job.pk).exists()


# The demo accounts (R5, R6, D5, D6; AC6, AC9)


def test_every_demo_account_logs_in_with_the_password_and_gets_no_email(client):
    """Each demo account works with the given password and has no confirmed address.

    1. Run seed_demo with a password
    2. Expect: every demo account is active, its email_verified_at is empty (so #27 never
       sends it an email), and logging in with the password succeeds
    """
    seed()

    assert demo_users().exists()
    for user in demo_users():
        assert user.is_active
        assert user.email_verified_at is None
        assert client.login(email=user.email, password=PASSWORD), user.email
        client.logout()


def test_without_password_option_the_command_asks_for_it(monkeypatch):
    """No --password: the password is typed, hidden, not passed on the command line.

    1. Replace getpass.getpass with one that records the call and returns "typed-pass"
    2. Run seed_demo without --password
    3. Expect: getpass was called; the demo accounts take "typed-pass"
    """
    asked = []

    def fake_getpass(prompt=""):
        asked.append(prompt)
        return "typed-pass"

    monkeypatch.setattr(getpass, "getpass", fake_getpass)

    call_command("seed_demo", stdout=io.StringIO())

    assert asked
    assert demo_users().first().check_password("typed-pass")


def test_report_lists_every_demo_login_but_not_the_password():
    """The command prints the demo logins, so they are documented without the repo.

    1. Run seed_demo, keep its report
    2. Expect: every demo address is in the report; the password is not
    """
    report = io.StringIO()

    call_command("seed_demo", password=PASSWORD, stdout=report)

    assert demo_users().exists()
    for email in demo_users().values_list("email", flat=True):
        assert email in report.getvalue()
    assert PASSWORD not in report.getvalue()


# What the command must not do (R7, R8, D9, D13; AC7, AC8)


def test_seed_sends_no_email_and_caches_no_translation():
    """Seeding is silent: no email goes out and the fake translator saves nothing.

    1. Run seed_demo
    2. Expect: the outbox is empty; the translation cache has no row
    """
    seed()

    assert mail.outbox == []
    assert not Translation.objects.exists()


def test_a_failure_half_way_leaves_the_old_demo_data(monkeypatch):
    """One transaction: an error while creating rolls back the deleting too.

    1. Run seed_demo, keep the ids of the demo accounts
    2. Make saving a review fail, run seed_demo again
    3. Expect: the command raises; the same demo accounts (same ids) and counts as after
       the first run
    """
    seed()
    before_ids = set(demo_users().values_list("pk", flat=True))
    before = counts()

    def broken_save(self, *args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(Review, "save", broken_save)

    with pytest.raises(RuntimeError):
        seed()

    assert set(demo_users().values_list("pk", flat=True)) == before_ids
    assert counts() == before


# Photos only into a local database (R11, D17; AC11)


def test_seed_adds_drawn_photos_with_thumbnails_to_a_local_database():
    """Locally the demo jobs get photos, so mentors see the photo gallery and thumbnails.

    1. Run seed_demo; the test database is on localhost
    2. Expect: some open demo jobs have photos; each photo and its thumbnail file exist in
       the storage
    """
    seed()

    photos = JobPhoto.objects.filter(job__employer__in=demo_users())
    assert photos.exists()
    for photo in photos:
        assert photo.image.storage.exists(photo.image.name)
        assert photo.thumbnail.storage.exists(photo.thumbnail.name)


def test_seed_adds_no_photos_to_a_remote_database(monkeypatch):
    """Run against Supabase with local settings, files would land on my disk: no photos.

    1. Make the database look remote: its host is a Supabase address
    2. Run seed_demo
    3. Expect: the demo jobs exist but have no photos; the report says photos were skipped
    """
    monkeypatch.setitem(
        connection.settings_dict, "HOST", "aws-0-eu-central-1.pooler.supabase.com"
    )
    report = io.StringIO()

    call_command("seed_demo", password=PASSWORD, stdout=report)

    assert Job.objects.filter(employer__in=demo_users()).exists()
    assert not JobPhoto.objects.filter(job__employer__in=demo_users()).exists()
    assert "photos skipped" in report.getvalue().lower()

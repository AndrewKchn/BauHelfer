"""Integration tests: the User admin through the Django test client (#8)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = "s3cret-pass-123"


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(email="admin@example.com", password=PASSWORD)


@pytest.fixture
def logged_in_client(client, admin_user):
    client.force_login(admin_user)
    return client


def test_admin_login_with_email_in_any_case(client, admin_user):
    response = client.post(
        reverse("admin:login"),
        # The admin login form calls its field "username", whatever USERNAME_FIELD is.
        {"username": "Admin@Example.com", "password": PASSWORD, "next": "/admin/"},
    )

    assert response.status_code == 302
    assert response.url == "/admin/"
    assert client.get("/admin/").context["user"] == admin_user


def test_admin_login_with_wrong_password_fails(client, admin_user):
    response = client.post(
        reverse("admin:login"),
        {"username": "admin@example.com", "password": "wrong", "next": "/admin/"},
    )

    assert response.status_code == 200  # the form is shown again with an error
    assert not response.context["user"].is_authenticated


def test_non_staff_user_cannot_open_admin(client):
    worker = User.objects.create_user(email="worker@example.com", password=PASSWORD)
    client.force_login(worker)

    response = client.get(reverse("admin:accounts_user_changelist"))

    assert response.status_code == 302
    assert reverse("admin:login") in response.url


def test_user_list_shows_users_and_searches_by_email(logged_in_client):
    User.objects.create_user(email="anna@example.com", password=PASSWORD)
    User.objects.create_user(email="boris@example.com", password=PASSWORD)
    url = reverse("admin:accounts_user_changelist")

    response = logged_in_client.get(url)
    assert response.status_code == 200
    assert "anna@example.com" in response.text
    assert "boris@example.com" in response.text

    response = logged_in_client.get(url, {"q": "anna"})
    assert "anna@example.com" in response.text
    assert "boris@example.com" not in response.text


def test_add_user_with_email_and_password(logged_in_client):
    response = logged_in_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "New.Worker@Example.com",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 302  # redirect to the new user's page
    user = User.objects.get(email="new.worker@example.com")  # stored lowercase
    assert user.check_password(PASSWORD)
    assert not user.is_staff


def test_add_user_rejects_email_that_differs_only_in_case(logged_in_client):
    User.objects.create_user(email="anna@example.com", password=PASSWORD)

    response = logged_in_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "ANNA@example.com",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 200  # the form is shown again with an error
    assert "email" in response.context["adminform"].form.errors
    assert User.objects.filter(email__iexact="anna@example.com").count() == 1


def test_edit_user_profile_fields(logged_in_client):
    user = User.objects.create_user(email="anna@example.com", password=PASSWORD)
    url = reverse("admin:accounts_user_change", args=[user.pk])

    # The change page posts every field; unchecked boxes (is_staff…) are simply left out.
    response = logged_in_client.post(
        url,
        {
            "email": "anna@example.com",
            "name": "Anna Kowalska",
            "phone": "+49 151 1234567",
            "role": "worker",
            "preferred_language": "pl",
            "work_permit_confirmed": "on",
            "is_active": "on",
            # date_joined is shown as two inputs: date and time.
            "date_joined_0": user.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": user.date_joined.strftime("%H:%M:%S"),
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    user.refresh_from_db()
    assert user.name == "Anna Kowalska"
    assert user.phone == "+49 151 1234567"
    assert user.role == User.Role.WORKER
    assert user.preferred_language == "pl"
    assert user.work_permit_confirmed is True

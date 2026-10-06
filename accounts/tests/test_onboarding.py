"""Unit tests: role choice form, onboarding middleware and profile link (#10).

Spec: docs/specs/onboarding.md (requirements R1-R11, decisions D1-D5).
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from accounts.forms import RoleForm
from accounts.middleware import OnboardingMiddleware

pytestmark = [pytest.mark.django_db, pytest.mark.story(10)]

User = get_user_model()


# Role form (R4, R7, D5)


def test_role_form_has_only_the_role_field():
    """The role form can change the role and nothing else.

    1. Open an empty role form
    2. Expect: only the field role
    """
    assert list(RoleForm().fields) == ["role"]


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_role_form_saves_a_valid_role(role):
    """Choosing worker or employer saves that role on the user.

    1. Submit the role form with role = worker / employer
    2. Expect: the form is valid and the user has that role in the database
    """
    user = User.objects.create_user(email="anna@example.com", password="x")

    form = RoleForm({"role": role}, instance=user)

    assert form.is_valid()
    form.save()
    user.refresh_from_db()
    assert user.role == role


@pytest.mark.parametrize("value", ["", "admin"])
def test_role_form_rejects_an_empty_or_unknown_role(value):
    """An empty or unknown role is an error and is not saved.

    1. Submit the role form with role = "" / "admin"
    2. Expect: the form is invalid with an error on role
    """
    # The model allows an empty role (admins have none); the form must not (D5).
    user = User.objects.create_user(email="anna@example.com", password="x")

    form = RoleForm({"role": value}, instance=user)

    assert not form.is_valid()
    assert "role" in form.errors


def test_role_form_ignores_other_fields():
    """Extra fields sent with the form, like is_staff, are ignored.

    1. Submit the role form with role = worker and is_staff = on
    2. Expect: the role is saved, the user is still not staff
    """
    user = User.objects.create_user(email="anna@example.com", password="x")

    form = RoleForm({"role": "worker", "is_staff": "on"}, instance=user)
    form.is_valid()
    form.save()

    user.refresh_from_db()
    assert user.is_staff is False


# Profile link (R5, D3)


@pytest.mark.parametrize(
    ("role", "url_name"),
    [
        ("worker", "worker_profile_edit"),
        ("employer", "employer_profile_edit"),
        ("", "role_select"),
    ],
)
def test_profile_url_depends_on_the_role(role, url_name):
    """Each role has its own profile form; without a role it is the role choice.

    1. Take a user with role worker / employer / none
    2. Expect: get_profile_url() is the worker / employer profile form / role choice
    """
    user = User(email="anna@example.com", role=role)

    assert user.get_profile_url() == reverse(url_name)


# Onboarding middleware (R1-R3, D1)


def run_middleware(user, path):
    """Send one request for `path` as `user` through the middleware.

    The "view" behind it just answers "view reached", so a test can tell whether the
    middleware let the request through or answered with a redirect itself.
    """
    request = RequestFactory().get(path)
    request.user = user
    middleware = OnboardingMiddleware(lambda request: HttpResponse("view reached"))
    return middleware(request)


def test_middleware_sends_a_user_without_role_to_the_role_choice():
    """A logged-in user without a role is sent to the role choice.

    1. As a user without a role, open the home page
    2. Expect: redirect to the role choice page
    """
    response = run_middleware(User(email="anna@example.com"), "/")

    assert response.status_code == 302
    assert response.url == reverse("role_select")


@pytest.mark.parametrize("url_name", ["role_select", "logout"])
def test_middleware_lets_a_user_without_role_open_the_allowed_pages(url_name):
    """Without a role the user can still choose a role and log out.

    1. As a user without a role, open the role choice / the logout URL
    2. Expect: the request reaches the view, no redirect
    """
    # Without role_select here, the role page would redirect to itself forever.
    response = run_middleware(User(email="anna@example.com"), reverse(url_name))

    assert response.content == b"view reached"


@pytest.mark.parametrize("path", ["/admin/", "/admin/login/"])
def test_middleware_does_not_block_the_admin_pages(path):
    """The admin pages are never blocked by onboarding.

    1. As a user without a role, open /admin/ and /admin/login/
    2. Expect: the request reaches the view (the admin checks access itself)
    """
    response = run_middleware(User(email="anna@example.com"), path)

    assert response.content == b"view reached"


@pytest.mark.parametrize(
    "user",
    [
        pytest.param(AnonymousUser(), id="guest"),
        pytest.param(User(email="boss@example.com", is_staff=True), id="staff"),
        pytest.param(User(email="anna@example.com", role="worker"), id="worker"),
        pytest.param(User(email="ben@example.com", role="employer"), id="employer"),
    ],
)
def test_middleware_lets_guests_staff_and_users_with_a_role_through(user):
    """Guests, admins and users who chose a role are not stopped.

    1. As a guest / staff without a role / worker / employer, open the home page
    2. Expect: the request reaches the view, no redirect
    """
    response = run_middleware(user, "/")

    assert response.content == b"view reached"

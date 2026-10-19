"""Helpers shared by the E2E test files: screen sizes, logging in, the "fits the screen" check.

Not a test file (no `test_` prefix): the test files import from here (moved out of
test_account_flows.py in #21, when a second E2E file needed them).
"""

# Most workers use a phone, many employers a laptop.
PHONE = {"width": 360, "height": 740}  # a small Android phone; base.html fits 360 px
LAPTOP = {"width": 1366, "height": 768}  # a common laptop screen

PASSWORD = "Gerüst-2026-Munich"


def log_in(page, email, password=PASSWORD):
    """Log in through the "Log in" link in the header."""
    page.goto("/")
    page.get_by_role("link", name="Log in").click()
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in").click()


def assert_fits_the_screen(page):
    """The page is not wider than the screen: no sideways scrolling on a phone."""
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow == 0, f"{page.url} is {overflow}px wider than the screen"

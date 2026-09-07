"""Literals shared between the test suite and scripts/ensure_test_user.py.

The bootstrap script writes this account into the test database; the auth tests
log in with it. Keeping the values in one place means a change can't leave the
two halves disagreeing.
"""

# Must match scripts/ensure_test_user.py.
TEST_USER_EMAIL = "test@promptiq.test"
TEST_USER_PASSWORD = "TestPassword123!"

# The httpOnly cookie the backend sets at login (settings.access_cookie_name).
# Hardcoded rather than read from settings on purpose: if someone renames the
# setting, the auth tests should fail loudly instead of silently following it.
ACCESS_COOKIE_NAME = "promptiq_access_token"

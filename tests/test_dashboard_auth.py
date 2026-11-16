# FILE GUIDE: Unit tests for the dashboard login credential check (no Streamlit needed).

"""Tests for DashboardAuth."""
from __future__ import annotations

import unittest

from campus_safety.dashboard.dashboard_auth import DashboardAuth


class DashboardAuthTests(unittest.TestCase):

    def test_default_credentials_are_admin_admin123(self) -> None:
        auth = DashboardAuth.from_env({})
        self.assertTrue(auth.check("admin", "admin123"))

    def test_wrong_username_or_password_is_rejected(self) -> None:
        auth = DashboardAuth.from_env({})
        self.assertFalse(auth.check("admin", "wrong"))
        self.assertFalse(auth.check("root", "admin123"))
        self.assertFalse(auth.check("", ""))

    def test_password_is_case_sensitive(self) -> None:
        self.assertFalse(DashboardAuth.from_env({}).check("admin", "ADMIN123"))

    def test_username_surrounding_spaces_are_ignored(self) -> None:
        self.assertTrue(DashboardAuth.from_env({}).check("  admin ", "admin123"))

    def test_environment_overrides_defaults(self) -> None:
        auth = DashboardAuth.from_env({"DASHBOARD_USERNAME": "officer",
                                       "DASHBOARD_PASSWORD": "S3cure!"})
        self.assertTrue(auth.check("officer", "S3cure!"))
        self.assertFalse(auth.check("admin", "admin123"))


if __name__ == "__main__":
    unittest.main()

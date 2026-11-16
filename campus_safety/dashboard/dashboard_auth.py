# FILE GUIDE: Login gate for the Streamlit dashboard.
# Credentials come from DASHBOARD_USERNAME / DASHBOARD_PASSWORD in .env
# (default admin / admin123). The check itself has no Streamlit dependency,
# so it can be unit tested; require_login() draws the login form.

"""Simple username/password login for the operations dashboard."""
from __future__ import annotations

import hmac
import os
from typing import Mapping

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"
SESSION_KEY = "dashboard_user"


class DashboardAuth:
    """Check dashboard credentials and keep the signed-in user in the session."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DashboardAuth":
        """Read credentials from the environment, falling back to the defaults."""
        env = os.environ if env is None else env
        username = (env.get("DASHBOARD_USERNAME") or "").strip() or DEFAULT_USERNAME
        password = env.get("DASHBOARD_PASSWORD") or DEFAULT_PASSWORD
        return cls(username, password)

    def check(self, username: str, password: str) -> bool:
        """Return True only if both values match (constant-time comparison)."""
        user_ok = hmac.compare_digest(str(username).strip().encode(), self._username.encode())
        pass_ok = hmac.compare_digest(str(password).encode(), self._password.encode())
        return user_ok and pass_ok

    def require_login(self) -> bool:
        """Show the login form until the user signs in; return True once signed in."""
        import streamlit as st

        user = st.session_state.get(SESSION_KEY)
        if user:
            with st.sidebar:
                st.caption(f"Signed in as **{user}**")
                if st.button("Log out", use_container_width=True):
                    st.session_state.pop(SESSION_KEY, None)
                    st.rerun()
            return True

        _, middle, _ = st.columns([1, 1.2, 1])
        with middle:
            st.markdown("### Campus Safety Operations")
            st.caption("Sign in to continue")
            with st.form("dashboard_login"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                if self.check(username, password):
                    st.session_state[SESSION_KEY] = username.strip()
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")
        return False

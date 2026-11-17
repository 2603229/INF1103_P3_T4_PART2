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

# Presentation only: styles the login screen, which shows before the dashboard's
# own STYLE is loaded. Colours and fonts match dashboard_oop.STYLE.
# Full-width split screen: navy brand panel on the left, sign-in form on the right.
LOGIN_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@700;800&display=swap');
.stApp {background:#F5F8FC;font-family:'DM Sans',sans-serif;}
#MainMenu, footer, [data-testid="stHeader"] {display:none;}
[data-testid="stMainBlockContainer"], .block-container {max-width:none !important;padding:0 !important;}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"],
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:0 !important;}
.cs-login-panel {min-height:100vh;box-sizing:border-box;background:#14273F;color:#E5EDF7;
  padding:3.5rem clamp(2rem,5vw,5rem);display:flex;flex-direction:column;gap:2.5rem;}
.cs-login-brand {display:flex;gap:0.85rem;align-items:center;}
.cs-login-mark {width:46px;height:46px;border-radius:12px;background:#319CC1;color:#FFF;
  font:800 1rem 'Manrope',sans-serif;display:flex;align-items:center;justify-content:center;}
.cs-login-name {font:800 1.12rem 'Manrope',sans-serif;color:#FFF;line-height:1.2;}
.cs-login-sub {font-size:0.7rem;letter-spacing:0.12em;text-transform:uppercase;color:#ABC0D3;margin-top:3px;}
.cs-login-hero {margin-top:auto;max-width:520px;}
.cs-login-hero h2 {font:800 clamp(2rem,3vw,2.75rem) 'Manrope',sans-serif;line-height:1.15;
  letter-spacing:-0.03em;color:#FFF;margin:0;padding:0;}
.cs-login-hero p {font-size:1.05rem;line-height:1.65;color:#C7D6E5;margin:1.1rem 0 0;}
.cs-login-points {list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:0.85rem;}
.cs-login-points li {display:flex;gap:0.7rem;align-items:center;color:#D2DFEC;font-size:0.98rem;margin:0;}
.cs-login-points svg {flex:none;}
.st-key-cs_login_card {max-width:440px;width:100%;margin:0 auto;padding:3rem 2rem;box-sizing:border-box;}
.cs-login-heading {font:800 2rem 'Manrope',sans-serif;letter-spacing:-0.02em;color:#17324D;margin:0;padding:0;}
.cs-login-help {color:#4F6378;font-size:0.98rem;margin:0.5rem 0 1.5rem;}
.cs-login-help code {font-size:0.85rem;background:#E9EEF4;color:#17324D;padding:2px 7px;border-radius:5px;}
[data-testid="stForm"] {background:#FFF;border:1px solid #E2E9F1;border-radius:16px;
  padding:1.8rem 1.6rem;box-shadow:0 10px 30px rgba(23,50,77,0.08);}
[data-testid="stForm"] input {border-radius:10px;min-height:2.6rem;}
[data-testid="stFormSubmitButton"] button {background:#176B9C !important;border-color:#176B9C !important;
  min-height:48px;border-radius:10px;font-weight:700;margin-top:0.4rem;}
[data-testid="stFormSubmitButton"] button:hover {background:#10557D !important;border-color:#10557D !important;}
[data-testid="stFormSubmitButton"] button * {color:#FFF !important;}
.cs-login-foot {text-align:center;color:#5B6E82;font-size:0.82rem;margin-top:1.4rem;}
@media (max-width:640px) {
  .cs-login-panel {min-height:auto;padding:2rem 1.5rem;gap:1.5rem;}
  .cs-login-hero h2 {font-size:1.6rem;}
  .cs-login-points {display:none;}
  .st-key-cs_login_card {padding:2rem 1rem;}
}
</style>
"""

_CHECK = ('<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" '
          'stroke="#48AFD1" stroke-width="2.4"><path d="M5 12l5 5L20 7"/></svg>')

LOGIN_PANEL = f"""
<div class="cs-login-panel">
  <div class="cs-login-brand"><div class="cs-login-mark">CS</div>
    <div><div class="cs-login-name">Campus Safety</div><div class="cs-login-sub">Operations console</div></div></div>
  <div class="cs-login-hero">
    <h2>Every hazard reported, prioritised and tracked.</h2>
    <p>Review AI-assessed incident reports, update their status and keep an audit trail of every decision.</p>
  </div>
  <ul class="cs-login-points">
    <li>{_CHECK}Priority queue ranked by risk score</li>
    <li>{_CHECK}Status history and human AI review</li>
    <li>{_CHECK}CSV export and database backups</li>
  </ul>
</div>
"""

LOGIN_HEADER = """
<h1 class="cs-login-heading">Sign in</h1>
<p class="cs-login-help">Use the dashboard credentials set in your <code>.env</code> file.</p>
"""


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
            # Keyed container: the dashboard CSS moves it to the bottom of the sidebar.
            with st.sidebar.container(key="cs_account"):
                st.caption(f"Signed in as **{user}**")
                if st.button("Log out", icon=":material/logout:", width="stretch"):
                    st.session_state.pop(SESSION_KEY, None)
                    st.rerun()
            return True

        st.markdown(LOGIN_STYLE, unsafe_allow_html=True)
        panel, form_side = st.columns([1.15, 1], vertical_alignment="center")
        with panel:
            st.markdown(LOGIN_PANEL, unsafe_allow_html=True)
        with form_side, st.container(key="cs_login_card"):
            st.markdown(LOGIN_HEADER, unsafe_allow_html=True)
            with st.form("dashboard_login"):
                username = st.text_input("Username", autocomplete="username")
                password = st.text_input("Password", type="password", autocomplete="current-password")
                submitted = st.form_submit_button("Sign in", width="stretch")
            if submitted:
                if self.check(username, password):
                    st.session_state[SESSION_KEY] = username.strip()
                    st.rerun()
                else:
                    st.error("Incorrect username or password.", icon=":material/error:")
            st.markdown('<p class="cs-login-foot">Local console · Singapore time (SGT)</p>',
                        unsafe_allow_html=True)
        return False

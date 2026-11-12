"""Campus Safety Operations Console -- Streamlit OOP management dashboard.

Run: python -m streamlit run dashboard_oop.py

This module only handles presentation and user interaction. The uploaded
DataManager and domain classes remain the authorities for CRUD, validation,
status audit entries and saved AI reviews. New presentation-only capabilities
live in dashboard_extensions.py; the new asynchronous CSV service lives in
campus_safety/services/background_export_service.py.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
import os
from pathlib import Path
from textwrap import wrap as wrap_text
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.data_manager.repository_factory import create_repository
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.domain.schema import VALID_STATUSES
from campus_safety.domain.ai_review_entry import REVIEW_DECISIONS
from campus_safety.dashboard.background_export_service import BackgroundExportService
from dashboard_extensions import (
    count_by, filter_reports, format_sg_time, monthly_counts,
    overview_metrics, parse_report_time, priority_score,
    resolve_evidence_image, safe_html, text,
    demo_records_present, demo_storage_configured,
)

PROJECT_ROOT = Path(__file__).resolve().parent
NAVIGATION = ("Overview", "Incidents", "Insights", "Data & backups")
SORT_OPTIONS = (
    "Highest risk first", "Newest first", "Oldest first",
    "Lowest risk first", "Location A–Z",
)

st.set_page_config(
    page_title="Campus Safety | Operations",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# PRESENTATION STYLING -- visual treatment; never a business-logic component.
# ---------------------------------------------------------------------------
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap');
:root {color-scheme: light; --cs-ink:#192E45; --cs-muted:#64768B; --cs-edge:#E4EAF1; --cs-bg:#F7F9FC; --cs-accent:#176B9C;}
html, body, [class*="css"], .stApp {font-family:'DM Sans',sans-serif;}
.stApp, [data-testid="stAppViewContainer"] > .main {background:var(--cs-bg);color:var(--cs-ink);}
/* Streamlit's floating header overlays the top of the document on some versions.
   Set padding on the current container AND its legacy class to prevent clipping. */
[data-testid="stMainBlockContainer"], .block-container {
  max-width:1450px; padding-top:5.15rem !important; padding-bottom:2.8rem !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:0.8rem;}
[data-testid="stSidebar"] {background:#14273F;border-right:1px solid #233D58;}
[data-testid="stSidebar"] * {color:#E5EDF7;}
[data-testid="stSidebar"] hr {border-color:#29445E;margin:1.15rem 0;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color:#AEC0D2;}
[data-testid="stSidebar"] [data-testid="stButton"] button {
  justify-content:flex-start;text-align:left;font-weight:650;border-radius:9px;
  min-height:2.6rem;padding:0.5rem 0.8rem;border:1px solid transparent;
  box-shadow:none;transition:background .15s ease;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {
  background:transparent;color:#D2DFEC;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover {
  background:#213C58;color:#FFF;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
  background:#2B4F6E;border-left:3px solid #48AFD1;color:#FFF;
}
[data-testid="stSidebar"] [data-testid="stToggle"] p {color:#E1EAF4;}
#MainMenu, footer {visibility:hidden;}
h1, h2, h3 {font-family:'Manrope',sans-serif;letter-spacing:-0.03em;}
[data-testid="stButton"] button {border-radius:9px;font-weight:650;min-height:2.5rem;}
[data-testid="stButton"] button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background:#176B9C;border-color:#176B9C;color:#FFF;
}
[data-testid="stButton"] button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {background:#145A83;border-color:#145A83;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  border-radius:9px;border-color:#DCE5EE;
}
[data-testid="stTabs"] [role="tab"] {font-weight:650;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {color:#176B9C;}
[data-testid="stDataFrame"] {border:1px solid #E2E9F1;border-radius:11px;overflow:hidden;}
[data-testid="stAlert"] {border-radius:10px;}
[data-testid="stExpander"] {border-radius:10px;border-color:#DEE6EF;}
[data-testid="stMetric"] {background:#FFF;border:1px solid #E5EAF0;padding:0.9rem;border-radius:12px;}
.cs-brand {display:flex;gap:0.78rem;align-items:center;margin:0.35rem 0 1.8rem;}
.cs-brandmark {width:40px;height:40px;background:#319CC1;border-radius:11px;
  display:flex;align-items:center;justify-content:center;font:800 0.94rem 'Manrope';color:white !important;}
.cs-brandhead {font:800 1.03rem 'Manrope';line-height:1.25;color:#FFF !important;}
.cs-brandsub {font-size:0.65rem;color:#ABC0D3 !important;letter-spacing:0.12em;text-transform:uppercase;margin-top:3px;}
.cs-side-label {font-size:0.69rem;letter-spacing:0.13em;text-transform:uppercase;color:#A8BDD2 !important;margin:0.35rem 0 0.35rem;}
.cs-sidebar-note {color:#AFC0D1 !important;font-size:0.78rem;line-height:1.5;}
.cs-page-header {margin:0.2rem 0 0.8rem;padding:0.4rem 0 0.2rem;overflow:visible;}
.cs-eyebrow {display:block;font-size:0.68rem;color:#3B7E9D;letter-spacing:0.13em;
  font-weight:800;text-transform:uppercase;line-height:1.6;margin:0 0 0.38rem;}
.cs-title {display:block;font:800 clamp(1.78rem,2.2vw,2.2rem) 'Manrope';line-height:1.25;
  letter-spacing:-0.045em;color:#192D43;margin:0 0 0.45rem;overflow:visible;}
.cs-subtitle {font-size:0.9rem;color:#62768B;line-height:1.55;margin:0 0 0.6rem;}
.cs-meta {display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center;font-size:0.75rem;color:#74859A;}
.cs-meta-dot {width:3px;height:3px;border-radius:50%;background:#A8B8C8;display:inline-block;}
.cs-section {font:750 1.13rem 'Manrope';letter-spacing:-0.027em;color:#192E45;margin:1.1rem 0 0.25rem;}
.cs-caption {font-size:0.81rem;color:#7A899B;margin:0 0 0.65rem;}
.cs-metric {background:#FFF;border:1px solid #E2E9F0;border-radius:13px;
  padding:1rem 1.1rem;min-height:118px;}
.cs-metric-label {color:#6E8094;font-size:0.71rem;font-weight:800;letter-spacing:0.07em;text-transform:uppercase;}
.cs-metric-value {font:800 2rem 'Manrope';line-height:1.2;letter-spacing:-0.05em;margin:0.4rem 0 0.15rem;color:#1F354E;}
.cs-metric-note {font-size:0.75rem;color:#8291A1;}
.cs-metric-tone-teal {border-top:3px solid #379A98;}
.cs-metric-tone-amber {border-top:3px solid #D59A45;}
.cs-metric-tone-rose {border-top:3px solid #D47982;}
.cs-metric-tone-blue {border-top:3px solid #4C88C2;}
.cs-flat-banner {background:#EAF1F7;border:1px solid #D9E6F0;border-radius:12px;
  padding:0.84rem 1rem;color:#335873;font-size:0.86rem;line-height:1.5;margin:0.3rem 0 0.4rem;}
.cs-flat-banner strong {color:#24475F;}
.cs-notice {background:#FFF6E5;border:1px solid #F5E5C4;border-radius:9px;
  padding:0.75rem 0.95rem;color:#805C27;font-size:0.85rem;line-height:1.55;margin:0.3rem 0 0.55rem;}
.cs-notice strong {color:#704916;}
.cs-pill {display:inline-flex;align-items:center;padding:0.23rem 0.57rem;border-radius:999px;
  font-weight:750;font-size:0.72rem;background:#EBF2F7;color:#426781;white-space:nowrap;}
.cs-pill.critical,.cs-pill.high {background:#FAE6E8;color:#AA4550;}
.cs-pill.medium {background:#FFF1D5;color:#90601F;}
.cs-pill.low {background:#E2F2EA;color:#2F7558;}
.cs-pill.pending-review {background:#F1EAF8;color:#7853A1;}
.cs-pill.in-progress {background:#E7EFFB;color:#365F94;}
.cs-pill.resolved,.cs-pill.closed {background:#DCF0E5;color:#2E7553;}
.cs-inlinebox {background:#FFF;border:1px solid #E5EAF0;padding:0.8rem 0.92rem;
  border-radius:10px;margin:0.08rem 0 0.45rem;min-height:65px;}
.cs-fieldlabel {font-size:0.68rem;letter-spacing:0.06em;font-weight:800;color:#8191A5;text-transform:uppercase;margin-bottom:0.28rem;}
.cs-fieldvalue {font-size:0.9rem;font-weight:550;color:#233A51;line-height:1.5;overflow-wrap:anywhere;}
.cs-banner {background:#EAF1F7;color:#3A607A;padding:0.73rem 0.95rem;border-radius:9px;font-size:0.84rem;margin:0.45rem 0;}
.cs-empty {border:1px dashed #BFCDDA;border-radius:12px;background:#FFF;padding:2.3rem 1rem;text-align:center;color:#71849B;}
.cs-empty strong {color:#243E55;display:block;font-size:1.08rem;margin-bottom:0.35rem;}
.cs-footer {padding-top:1.2rem;color:#8D9BAC;font-size:0.73rem;text-align:center;}
.cs-table-wrap {border:1px solid #E2E9F1;background:#FFF;border-radius:12px;overflow-x:auto;}
.cs-table {border-collapse:collapse;width:100%;font-size:0.83rem;table-layout:auto;}
.cs-table th {background:#F3F6F9;color:#6C7F95;text-align:left;padding:0.78rem 0.9rem;
  font-size:0.68rem;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;}
.cs-table td {padding:0.72rem 0.9rem;border-top:1px solid #EBEFF4;color:#30445B;vertical-align:middle;line-height:1.4;}
.cs-table tr:hover td {background:#F9FBFD;}
.cs-table .cs-id {font-weight:750;color:#1E587E;white-space:nowrap;}
.cs-table .cs-small {font-size:0.76rem;color:#7C8B9C;white-space:nowrap;}
.cs-table .cs-loc {font-weight:650;color:#253B52;}
.cs-small-note {color:#7B8D9D;font-size:0.77rem;}
@media (max-width:900px) {
  [data-testid="stMainBlockContainer"],.block-container {padding-top:4.7rem !important;padding-bottom:2rem !important;}
  .cs-metric {min-height:110px;padding:0.88rem;}
  .cs-metric-value {font-size:1.75rem;}
  .cs-table th,.cs-table td {padding:0.62rem 0.7rem;}
}
</style>
"""

# ---------------------------------------------------------------------------
# UI-ONLY HELPERS -- no persistence, AI processing or domain state changes.
# ---------------------------------------------------------------------------
def _badge(value: Any) -> str:
    val = text(value, "Unassigned")
    css = val.lower().replace(" ", "-")
    if css not in {"critical", "high", "medium", "low", "pending-review", "in-progress", "resolved", "closed"}:
        css = "neutral"
    return f'<span class="cs-pill {css}">{escape(val)}</span>'


def _field(label: str, value: Any) -> None:
    st.markdown(
        f'<div class="cs-inlinebox"><div class="cs-fieldlabel">{escape(label)}</div>'
        f'<div class="cs-fieldvalue">{safe_html(value)}</div></div>',
        unsafe_allow_html=True,
    )


def _heading(label: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="cs-section">{escape(label)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="cs-caption">{escape(subtitle)}</div>', unsafe_allow_html=True)


def _toast(kind: str, message: str) -> None:
    st.session_state["cs_flash"] = (kind, message)


@st.cache_resource(show_spinner=False)
def _export_service() -> BackgroundExportService:
    return BackgroundExportService(max_workers=2)


@st.fragment(run_every="15s")
def _live_body(dashboard: "IncidentDashboard", page: str) -> None:
    """Refresh reads without blocking other widgets or requiring a live AI key."""
    dashboard._render_page_body(page)

# ---------------------------------------------------------------------------
# OOP DASHBOARD -- presentation layer associated with an injected DataManager.
# ---------------------------------------------------------------------------
class IncidentDashboard:
    """Present validated domain records; all mutations delegate to DataManager."""

    def __init__(self, data_manager: DataManager, backend: str = "json") -> None:
        self._data_manager = data_manager
        self._backend = backend.upper()

    def render(self) -> None:
        st.markdown(STYLE, unsafe_allow_html=True)
        page, live = self._sidebar()
        header_title = {
            "Overview": "Operations overview",
            "Incidents": "Incident workspace",
            "Insights": "Safety intelligence",
            "Data & backups": "Data & recovery",
        }[page]
        safe_to_refresh = page in {"Overview", "Insights"}
        refresh_label = (
            "Auto-refresh: 15s" if live and safe_to_refresh else "Manual refresh"
        )
        header, right = st.columns([5, 1], vertical_alignment="bottom", gap="medium")
        with header:
            st.markdown(
                '<header class="cs-page-header">'
                '<div class="cs-eyebrow">Campus safety / operations</div>'
                f'<h1 class="cs-title">{escape(header_title)}</h1>'
                '<p class="cs-subtitle">Review incidents, assess risks and maintain a clear record of every decision.</p>'
                '<div class="cs-meta">'
                f'<span>{escape(self._backend)} repository</span>'
                '<span class="cs-meta-dot"></span><span>Singapore time (SGT)</span>'
                f'<span class="cs-meta-dot"></span><span>{escape(refresh_label)}</span>'
                '</div></header>',
                unsafe_allow_html=True,
            )
        with right:
            if st.button("Refresh", icon=":material/refresh:", key="cs_refresh", width="stretch"):
                st.rerun()

        flash = st.session_state.pop("cs_flash", None)
        if flash:
            kind, message = flash
            if kind == "success":
                st.success(message, icon=None)
            elif kind == "warning":
                st.warning(message, icon=None)
            else:
                st.error(message, icon=None)

        # Form pages deliberately do not auto-refresh: a periodic fragment rerun
        # would disrupt partially completed status updates and AI reviews.
        if live and safe_to_refresh:
            _live_body(self, page)
        else:
            self._render_page_body(page)
        st.markdown(
            '<div class="cs-footer">Campus Safety Operations · Local incident management · '
            'Human AI reviews are informational, not authenticated decisions.</div>',
            unsafe_allow_html=True,
        )

    def _sidebar(self) -> tuple[str, bool]:
        with st.sidebar:
            st.markdown(
                '<div class="cs-brand"><div class="cs-brandmark">CS</div>'
                '<div><div class="cs-brandhead">Campus Safety</div>'
                '<div class="cs-brandsub">Operations console</div></div></div>',
                unsafe_allow_html=True,
            )
            request = st.session_state.pop("cs_nav_request", None)
            if request in NAVIGATION:
                st.session_state["cs_workspace"] = request
            page = st.session_state.get("cs_workspace", "Overview")
            if page not in NAVIGATION:
                page = "Overview"
            st.markdown('<div class="cs-side-label">WORKSPACE</div>', unsafe_allow_html=True)
            links = (
                ("Overview", ":material/space_dashboard:"),
                ("Incidents", ":material/fact_check:"),
                ("Insights", ":material/monitoring:"),
                ("Data & backups", ":material/folder_copy:"),
            )
            for label, icon in links:
                if st.button(label, icon=icon, width="stretch", key=f"cs_nav_{label}",
                             type="primary" if page == label else "secondary"):
                    if page != label:
                        st.session_state["cs_workspace"] = label
                        st.rerun()
            st.divider()
            st.markdown('<div class="cs-side-label">PREFERENCES</div>', unsafe_allow_html=True)
            live = st.toggle("Auto-refresh summaries", value=True, key="cs_autorefresh")
            st.markdown(
                '<p class="cs-sidebar-note">Overview and insights refresh every 15s. '
                'Incident forms remain stable while you work.</p>', unsafe_allow_html=True,
            )
            st.divider()
            st.markdown('<div class="cs-side-label">CURRENT STORAGE</div>', unsafe_allow_html=True)
            st.markdown(f"**{escape(self._backend)} repository**")
            st.markdown(
                '<p class="cs-sidebar-note">The data backend is configured locally. '
                'No Gemini calls are made by this dashboard.</p>', unsafe_allow_html=True,
            )
        return page, live
    
    def _render_page_body(self, page: str) -> None:
        try:
            reports = self._data_manager.load()
            records = [report.as_dict() for report in reports]
        except (DataStoreError, InvalidRecord, ValueError, OSError) as exc:
            st.error(f"Incident database unavailable: {exc}", icon=None)
            st.info("Check the selected backend, database path, permissions and record integrity. The database was not reset.")
            return

        # Integration pack never shows seeded records as operational incidents.
        # An older local database may still contain sample data from UI testing.
        if demo_records_present(records):
            st.error(
                "Sample incidents were detected in the selected database. "
                "This integration dashboard will not display them as real reports. "
                "Select the team's actual repository and database path.",
                icon=None,
            )
            return

        if page == "Overview":
            self._overview_section(records)
        elif page == "Incidents":
            self._incident_section(records)
        elif page == "Insights":
            self._insights_section(records)
        else:
            self._data_section(reports, records)

    def _metric_cards(self, records: Sequence[Mapping[str, Any]]) -> None:
        values = overview_metrics(records)
        config = (
            ("Total incidents", "total", "All historical records", "blue"),
            ("Active cases", "active", "Pending or in progress", "teal"),
            ("High-priority active", "high_priority", "Attention recommended", "rose"),
            ("Resolved / closed", "resolved", "Completed cases", "amber"),
        )
        for col, (label, key, note, tone) in zip(st.columns(4), config):
            with col:
                st.markdown(
                    f'<div class="cs-metric cs-metric-tone-{tone}">'
                    f'<div class="cs-metric-label">{escape(label)}</div>'
                    f'<div class="cs-metric-value">{values[key]}</div>'
                    f'<div class="cs-metric-note">{escape(note)}</div></div>',
                    unsafe_allow_html=True,
                )

    def _overview_section(self, records: list[dict[str, Any]]) -> None:
        st.markdown('<div class="cs-eyebrow">AT A GLANCE</div>', unsafe_allow_html=True)
        self._metric_cards(records)
        if not records:
            self._empty_state("No incidents recorded", "Submit a fictional report through the CLI; it will appear here when saved.")
            return
        stats = overview_metrics(records)
        if stats["high_priority"]:
            st.markdown(
                '<div class="cs-notice"><strong>Attention needed:</strong> '
                f'{stats["high_priority"]} active cases are rated high or critical. '
                'Review these incidents in the priority queue below.</div>',
                unsafe_allow_html=True,
            )

        col_left, col_right = st.columns([1.85, 1], gap="large")
        with col_left:
            _heading("Priority queue", "Open and manage the most urgent outstanding cases")
            active = [r for r in records if text(r.get("status"), "Pending Review") in {"Pending Review", "In Progress"}]
            active = filter_reports(active, sort="Highest risk first")[:8]
            if active:
                self._table(active, compact=True)
                if st.button("Open incident workspace", key="cs_overview_open", type="primary"):
                    st.session_state["cs_nav_request"] = "Incidents"
                    st.rerun()
            else:
                st.success("There are no active incidents.", icon=None)
        with col_right:
            _heading("Current workload", "Incident distribution by status")
            self._chart(count_by(records, "status"), label="Incidents")
            if stats["awaiting_ai_review"]:
                st.info(
                    f"{stats['awaiting_ai_review']} Gemini-assessed case(s) have no human AI review yet.",
                    icon=None,
                )

        _heading("Recently reported", "Five latest submissions · newest first")
        recent = filter_reports(records, sort="Newest first")[:5]
        self._recent_table(recent)

    @staticmethod
    def _recent_table(records: Sequence[Mapping[str, Any]]) -> None:
        """An exact, five-row recent-activity table (no virtualised blank rows)."""
        if not records:
            st.caption("No recent incidents.")
            return
        rows = []
        for item in records:
            identifier = safe_html(item.get("incident_id"))
            location = safe_html(item.get("location"))
            category = safe_html(item.get("category"))
            reported = escape(format_sg_time(item.get("timestamp")))
            rows.append(
                '<tr>'
                f'<td class="cs-id">{identifier}</td>'
                f'<td><span class="cs-loc">{location}</span><div class="cs-small">{category}</div></td>'
                f'<td class="cs-small">{reported}</td>'
                f'<td>{_badge(item.get("final_priority"))}</td>'
                f'<td>{_badge(item.get("status"))}</td>'
                '</tr>'
            )
        st.markdown(
            '<div class="cs-table-wrap"><table class="cs-table">'
            '<thead><tr><th>Case ID</th><th>Location / category</th>'
            '<th>Reported</th><th>Priority</th><th>Status</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>', unsafe_allow_html=True,
        )
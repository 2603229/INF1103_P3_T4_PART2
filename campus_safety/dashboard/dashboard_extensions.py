"""NEW DASHBOARD-ONLY EXTENSIONS (not present in the supplied DataManager).

Every function in this module is a presentation-side convenience function:
search/filtering, live KPI calculations, timezone display, and safe evidence
lookup. They do not modify the domain, business rules or persistence layer.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

SG_TIMEZONE = ZoneInfo("Asia/Singapore")
ACTIVE_STATUSES = {"Pending Review", "In Progress"}
HIGH_PRIORITIES = {"High", "Critical", "Urgent", "Immediate"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_EVIDENCE_BYTES = 12 * 1024 * 1024

def text(value: Any, fallback: str = "Not provided") -> str:
    """Convert a record value to nonempty display text."""
    if value is None or str(value).strip().lower() in {"", "none", "nan"}:
        return fallback
    return str(value)

def safe_html(value: Any) -> str:
    """Escape dynamic content before including it in a styled HTML fragment."""
    return escape(text(value), quote=True)

def parse_report_time(value: Any) -> datetime | None:
    """Read either legacy SGT timestamps or timezone-aware ISO timestamps."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=SG_TIMEZONE)
        return moment.astimezone(SG_TIMEZONE)
    except (ValueError, TypeError, OverflowError):
        return None
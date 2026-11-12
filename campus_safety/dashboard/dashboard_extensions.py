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
    
def format_sg_time(value: Any, include_seconds: bool = False) -> str:
    moment = parse_report_time(value)
    if moment is None:
        return text(value, "Unknown time")
    fmt = "%d %b %Y, %I:%M:%S %p" if include_seconds else "%d %b %Y, %I:%M %p"
    return moment.strftime(fmt) + " SGT"

def priority_score(row: Mapping[str, Any]) -> float:
    try:
        return float(row.get("priority_score") or 0)
    except (ValueError, TypeError):
        return 0.0
    
def filter_reports(
    reports: Sequence[Mapping[str, Any]],
    *,
    search: str = "",
    statuses: Sequence[str] = (),
    priorities: Sequence[str] = (),
    categories: Sequence[str] = (),
    date_start: date | None = None,
    date_end: date | None = None,
    sort: str = "Highest risk first",
) -> list[dict[str, Any]]:
    """Apply case-insensitive search, optional filters and stable sort."""
    needle = search.strip().casefold()
    result = []
    searchable = (
        "incident_id", "reporter_name", "location", "asset_info",
        "category", "severity", "description", "assigned_route",
    )
    for item in reports:
        row = dict(item)
        if needle and not any(needle in str(row.get(field) or "").casefold() for field in searchable):
            continue
        if statuses and text(row.get("status"), "Pending Review") not in statuses:
            continue
        if priorities and text(row.get("final_priority"), "Unassigned") not in priorities:
            continue
        if categories and text(row.get("category"), "Uncategorised") not in categories:
            continue
        if date_start or date_end:
            moment = parse_report_time(row.get("timestamp"))
            if moment is None:
                continue
            if date_start and moment.date() < date_start:
                continue
            if date_end and moment.date() > date_end:
                continue
        result.append(row)

    def timestamp(row: Mapping[str, Any]) -> float:
        moment = parse_report_time(row.get("timestamp"))
        return moment.timestamp() if moment else 0

    if sort == "Oldest first":
        result.sort(key=timestamp)
    elif sort == "Newest first":
        result.sort(key=timestamp, reverse=True)
    elif sort == "Lowest risk first":
        result.sort(key=lambda r: (priority_score(r), timestamp(r)))
    elif sort == "Location A–Z":
        result.sort(key=lambda r: text(r.get("location"), "").casefold())
    else:
        result.sort(key=lambda r: (priority_score(r), timestamp(r)), reverse=True)
    return result

def overview_metrics(reports: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Read-only operational indicators; no scoring policy is recalculated."""
    statuses = [text(r.get("status"), "Pending Review") for r in reports]
    active = sum(s in ACTIVE_STATUSES for s in statuses)
    high = sum(
        text(r.get("final_priority"), "").strip() in HIGH_PRIORITIES
        and text(r.get("status"), "Pending Review") in ACTIVE_STATUSES
        for r in reports
    )
    pending_ai_review = sum(
        r.get("assessment_source") == "Gemini AI"
        and not r.get("ai_review_history")
        for r in reports
    )
    return {
        "total": len(reports),
        "active": active,
        "high_priority": high,
        "resolved": sum(s in {"Resolved", "Closed"} for s in statuses),
        "pending_review": sum(s == "Pending Review" for s in statuses),
        "awaiting_ai_review": pending_ai_review,
    }

def count_by(reports: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(text(row.get(field), "Unspecified") for row in reports).most_common())

def monthly_counts(reports: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for report in reports:
        moment = parse_report_time(report.get("timestamp"))
        if moment:
            counts[moment.strftime("%Y-%m")] += 1
    return dict(sorted(counts.items()))

def resolve_evidence_image(raw_path: Any, allowed_roots: Sequence[Path]) -> Path | None:
    """Allow preview only of small image files inside approved data directories.

    This deliberately refuses absolute paths outside the project/data directory,
    including paths containing traversal segments in otherwise valid records.
    """
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    path = Path(raw_path)
    if path.suffix.casefold() not in IMAGE_EXTENSIONS:
        return None
    for root in allowed_roots:
        permitted = root.expanduser().resolve()
        candidate = (path if path.is_absolute() else permitted / path).resolve()
        if not candidate.is_relative_to(permitted):
            continue
        try:
            if candidate.is_file() and candidate.stat().st_size <= MAX_EVIDENCE_BYTES:
                return candidate
        except OSError:
            continue
    return None
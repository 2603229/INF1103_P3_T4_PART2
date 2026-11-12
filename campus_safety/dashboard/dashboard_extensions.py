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
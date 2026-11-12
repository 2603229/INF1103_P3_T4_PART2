"""Prepare incident CSV downloads in an isolated worker thread.

NEW SERVICE -- not provided by the uploaded prototype's DataManager.
The worker receives a defensive in-memory snapshot, never a repository, a
SQLite connection or a Streamlit session object.
"""

from __future__ import annotations

import csv
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from io import StringIO
import json
from typing import Any, Mapping, Sequence

from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.schema import SCHEMA_FIELDS

class BackgroundExportService:
    """Own a small executor and asynchronously serialise read-only snapshots."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="incident-csv"
        )

    def submit_csv(
        self, reports: Sequence[HazardReport | Mapping[str, Any]]
    ) -> Future[bytes]:
        """Create the snapshot before scheduling the worker for thread safety."""
        snapshot = [
            deepcopy(report.as_dict() if isinstance(report, HazardReport) else dict(report))
            for report in reports
        ]
        return self._executor.submit(self._render_csv, snapshot)
    
    @staticmethod
    def _csv_cell(value: Any) -> str | int | float:
        """Render nested fields and guard spreadsheet applications from formula injection."""
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value, ensure_ascii=False, default=str)
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float)):
            return value
        text = str(value)
        if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
            return "'" + text
        return text
"""Export incident snapshots to CSV or readable text files."""
from __future__ import annotations

import csv
from pathlib import Path

from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.domain.hazard_report import HazardReport


class IncidentExporter:
    """Write incident report collections to supported file formats."""

    def export_csv(self, reports: list[HazardReport],
                   destination: str | Path) -> Path:
        rows = [report.as_dict() for report in reports]
        if not rows:
            raise DataStoreError("No records to export")
        fields = list(dict.fromkeys(key for row in rows for key in row))
        path = Path(destination)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            return path
        except OSError as exc:
            raise DataStoreError("Cannot export CSV") from exc

    def export_txt(self, reports: list[HazardReport],
                   destination: str | Path) -> Path:
        rows = [report.as_dict() for report in reports]
        if not rows:
            raise DataStoreError("No records to export")
        path = Path(destination)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as stream:
                stream.write("CAMPUS SAFETY HAZARD REPORTING SYSTEM\nINCIDENT MANAGEMENT REPORT\n")
                stream.write(f"Total Incidents: {len(rows)}\n\n")
                for row in rows:
                    stream.write("-" * 50 + "\n")
                    for key, value in row.items():
                        display_value = value if value is not None else "N/A"
                        stream.write(
                            f"{key.replace('_', ' ').title()}: {display_value}\n"
                        )
            return path
        except OSError as exc:
            raise DataStoreError("Cannot export TXT") from exc

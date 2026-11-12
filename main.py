# FILE GUIDE: Program entry point (`python main.py`).
# All behaviour lives in classes; this file only starts CampusSafetyApplication
# and turns startup storage failures into a clear message and exit code.

"""Entry point for the Campus Safety Hazard Reporting System."""
from __future__ import annotations

import sys
from pathlib import Path

from campus_safety.application import CampusSafetyApplication
from campus_safety.data_manager.data_store_error import DataStoreError

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    """Start the CLI; return a process exit code (0 = success)."""
    try:
        app = CampusSafetyApplication.create_default(PROJECT_ROOT)
    except (DataStoreError, ValueError) as exc:
        print(f"[Startup Error] Incident database unavailable: {exc}", file=sys.stderr)
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# FILE GUIDE: Single-command local launcher (`python main.py`).
# Starts the Streamlit dashboard and the incident-submission CLI together.
# Use `python main.py --cli-only` to run the command-line interface alone.

"""Entry point for the integrated Campus Safety Hazard Reporting System."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from campus_safety.application import CampusSafetyApplication
from campus_safety.dashboard.launcher import DashboardLauncher, DashboardLaunchError
from campus_safety.data_manager.data_store_error import DataStoreError

PROJECT_ROOT = Path(__file__).resolve().parent
EXIT_INTERRUPTED = 130  # conventional exit code for Ctrl+C


def main(*, launch_dashboard: bool = True, open_browser: bool = True) -> int:
    """Start the reporting CLI and, by default, the dashboard in one command."""
    try:
        app = CampusSafetyApplication.create_default(PROJECT_ROOT)
    except (DataStoreError, ValueError) as exc:
        print(f"[Startup Error] Incident database unavailable: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStartup cancelled.", file=sys.stderr)
        return EXIT_INTERRUPTED

    launcher = None
    if launch_dashboard:
        launcher = DashboardLauncher(PROJECT_ROOT, open_browser=open_browser)
        try:
            url = launcher.start()
            print(f"\n[Dashboard] Starting at {url}" + (" (opening browser...)" if open_browser else " (browser launch disabled)"))
            print("[Dashboard] Runs alongside this CLI; both share the same incident database.")
            print("[Dashboard] Exiting the CLI will also stop the dashboard.\n")
        except DashboardLaunchError as exc:
            # Preserve the reporting CLI even when optional UI dependencies fail.
            print(f"[Dashboard] Not started: {exc}", file=sys.stderr)
            launcher = None
    try:
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\nApplication interrupted.", file=sys.stderr)
        return EXIT_INTERRUPTED
    finally:
        if launcher is not None:
            launcher.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Safety reporting + management dashboard")
    parser.add_argument("--cli-only", action="store_true", help="Run the reporting CLI without the dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Start the dashboard without opening a browser")
    options = parser.parse_args()
    sys.exit(main(launch_dashboard=not options.cli_only, open_browser=not options.no_browser))

"""
IO Manager Summary:
------------------
- Acts as the CLI presentation and input adapter, keeping all terminal input/output 
  responsibilities strictly separated from domain and business logic.
- Handles interactive user prompting, validation loops (e.g., regex matching for names and 
  SIT credentials), and numerical bounds checks.
- Manages optional image evidence attachments, supporting both graphical file pickers 
  (tkinter) and terminal fallback prompts with safe path copying and collision handling.
- Formats and displays dynamic menus, pre-submission reviews, AI priority score breakdowns, 
  incident lists, and frequent hazard rankings.
- Utilises dependency injection for read/write callables to support automated UI and headless testing.
"""

# Import statements for library modules and type hinting
from __future__ import annotations
from pathlib import Path
from typing import Callable
from typing import Any
from campus_safety.domain.decision import Decision
from campus_safety.domain.facility_summary_report import FacilitySummaryReport
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.schema import VALID_CATEGORIES, VALID_SEVERITIES, VALID_STATUSES
from campus_safety.io_manager.validators import InputValidator
from campus_safety.io_manager.media import MediaHandler

"""IO Manager: CLI interaction and presentation, isolated from domain logic."""


class IOManager:
    """Takes injectable input/output callables for automated UI tests."""

    # Configure injectable input/output callbacks and a resolved base directory.
    def __init__(self, read: Callable[[str], str] = input,
                 write: Callable[[str], None] = print,
                 base_dir: str | Path | None = None) -> None:
        
        # Store the read callable (defaults to built-in input) for interactive user prompts
        self._read: Callable[[str], str] = read
        
        # Store the write callable (defaults to built-in print) for rendering outputs
        self._write: Callable[[str], None] = write
        
        # Resolve and store the base directory path (defaults to current working directory) for safe file operations
        self._base_dir = Path(base_dir or Path.cwd()).resolve()

        # Composition: IOManager creates and owns its MediaHandler for image attachments
        self._media_handler = MediaHandler(read, write, self._base_dir)

    # Print user-facing CLI text through the configured output callback.
    def display_message(self, message: str) -> None:
        # Route all outgoing text messages through the injected write callable
        self._write(str(message))

    # Main Menu Interface
    def menu(self) -> str:
        self.display_message("\n==============================================\n"
                             " CAMPUS SAFETY HAZARD REPORTING SYSTEM\n"
                             "==============================================\n"
                             "1. Submit New Hazard Report\n"
                             "2. View All Logged Incidents\n"
                             "3. View Top 5 Most Frequent Hazards\n"
                             "4. Search and Filter Incidents\n"
                             "5. View Facilities Summary Report\n"
                             "6. Exit")
        while True:
            choice = self._read("Select an option (1-6): ").strip()
            if choice in ("1", "2", "3", "4", "5", "6"):
                return choice
            self.display_message("[Error] Enter a number between 1 and 6.")

    # Creates helper methods (_required and confirm) to safely loop through user prompts until valid text or affirmative/negative choices are given.
    def _required(self, prompt: str, check: Callable[[str], bool], error: str) -> str:
        while True:
            value = self._read(prompt).strip()
            if check(value):
                return value
            self.display_message("[Error] " + error)

    def confirm(self, prompt: str = "Confirm hazard report submission? (y/n): ") -> bool:
        while True:
            answer = self._read(prompt).strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.display_message("[Error] Enter y or n.")

    # Orchestrates step-by-step terminal input for reporter details, location, headcount, 
    # asset summary, and risk description using input validators.
    def get_user_input(self) -> HazardReport:
        self.display_message("\n--- Submit New Hazard Report (SIT Punggol Coast) ---")
        
        name = self._required("Enter reporter name (Student/Teacher): ",
                            InputValidator.validate_name, "Enter a valid name.")
        contact = self._required("Enter SIT email or phone number: ",
                               InputValidator.validate_contact,
                               "Enter a valid SIT email or 8-digit phone number.")
        location = self._required("Enter location: ",
                                InputValidator.validate_location, "Location cannot be empty.")
        people_str = self._required("Estimated number of people affected (1-1000): ",
                                    InputValidator.validate_headcount,
                                    "Enter a whole number between 1 and 1000.")
        people = int(people_str)
        asset = self._required("Enter asset or brief hazard summary: ",
                               InputValidator.validate_asset, "Minimum three characters required.")
        desc = self._required("Describe the risk/safety hazard: ",
                            InputValidator.validate_description, "Minimum 15 characters required.")

        # Connects the MediaHandler to attach optional images and bundles all collected fields into a HazardReport model instance.
        image = self._media_handler.attach_image(self.confirm)
        
        return HazardReport.from_input({
            "reporter_name": name, "reporter_contact": contact,
            "location": location, "impact_headcount": people,
            "asset_info": asset, "description": desc, "image_patch": image
        })

    # Displays calculation breakdowns for severity, operational impact, and frequency, along with the final priority score and classification.
    def priority_calculation(self, report: HazardReport, decision: Decision) -> None:
        b = decision.score_breakdown
        self.display_message("\n========== PRIORITY SCORE CALCULATION ==========\n"
                             f"Severity: {report.get('severity')} -> +{b['severity']}\n"
                             f"Operational Impact: {report.get('operational_impact')} -> +{b['operational_impact']}\n"
                             f"Historical Frequency: {report.get('historical_frequency')} -> +{b['historical_frequency']}\n"
                             f"Priority Score: {decision.score}\nFinal Priority: {decision.priority}")

    # Displays a pre-submission summary of the hazard report, allowing the user to review all entered information before final submission.
    def pre_submission_summary(self, report: HazardReport) -> None:
        self.display_message("\n========== PRE-SUBMISSION SUMMARY ==========")
        for key in ("location", "asset_info", "category", "severity", "operational_impact",
                    "assessment_source", "final_priority", "recommended_action", "is_duplicate"):
            self.display_message(f"{key.replace('_',' ').title()}: {report.get(key, 'N/A')}")

    # Formats and prints a detailed breakdown of the successfully saved incident report
    def submission_success(self, report: HazardReport) -> None:
        self.display_message(f"\n[Success] Incident saved: {report.incident_id}")
        for key in ("category", "severity", "operational_impact", "risk_summary",
                    "contextual_insights", "historical_frequency", "priority_score",
                    "final_priority", "recommended_action", "escalation_reason", "assigned_route",
                    "is_duplicate", "status"):
            self.display_message(f"{key.replace('_', ' ').title()}: {report.get(key, 'N/A')}")

    # Displays a list of all logged hazard reports, including their unique incident IDs and key details, 
    # or notifies the user if no reports are found.
    def view_all_reports(self, reports: list[HazardReport]) -> None:
        if not reports:
            self.display_message("[Notice] No hazard reports found.")
            return
        self.display_message(f"\nTotal Reports Found: {len(reports)}")
        # Display structered list of reports with their details, including incident ID, reporter info, location, headcount, asset info, description, severity, and status.
        for index, report in enumerate(reports, 1):
            self.display_message(f"--- Report #{index} ---")
            for key in ("incident_id", "reporter_name", "reporter_contact", "location",
                        "impact_headcount", "asset_info", "description", "severity", "status"):
                self.display_message(f"{key.replace('_', ' ').title()}: {report.get(key, 'N/A')}")

    # Displays the top 5 most frequently reported hazards, including their asset names and occurrence counts,
    # or notifies the user if no reports are found.
    def view_frequent_hazards(self, counts: list[tuple[str, int]]) -> None:
        self.display_message("\nTOP 5 MOST FREQUENT HAZARDS")
        if not counts:
            self.display_message("[Notice] No hazard reports found.")
            return
        for index, (name, count) in enumerate(counts, 1):
            self.display_message(f"{index}. {name} — {count} report(s)")

    # Asks for optional search filters; pressing Enter skips a filter.
    # Returns keyword arguments matching DataManager.search().
    def get_search_criteria(self) -> dict[str, Any]:
        self.display_message("\n--- Search and Filter Incidents (press Enter to skip a filter) ---")
        location = self._read("Location keyword: ").strip()
        status = self._choose_optional("Status", VALID_STATUSES)
        category = self._choose_optional("Category", VALID_CATEGORIES)
        severity = self._choose_optional("Minimum severity", VALID_SEVERITIES)
        return {
            "location_query": location,
            "status_filter": status,
            "category_filter": category,
            "min_severity": VALID_SEVERITIES.index(severity) + 1 if severity else 1,
        }

    # Shows numbered options and returns the chosen value, or "" when skipped.
    def _choose_optional(self, label: str, options: tuple[str, ...]) -> str:
        listing = ", ".join(f"{number}={value}" for number, value in enumerate(options, 1))
        while True:
            answer = self._read(f"{label} ({listing}): ").strip()
            if not answer:
                return ""
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]
            self.display_message(f"[Error] Enter a number from 1 to {len(options)}, or press Enter to skip.")

    # Displays matching incident dictionaries returned by DataManager.search().
    def view_search_results(self, results: list[dict[str, Any]]) -> None:
        if not results:
            self.display_message("[Notice] No incidents match your filters.")
            return
        self.display_message(f"\nMatching Incidents: {len(results)}")
        for record in results:
            self.display_message(
                f"- {record.get('incident_id') or 'N/A'} | {record.get('location') or 'N/A'} | "
                f"{record.get('category') or 'N/A'} | Severity: {record.get('severity') or 'N/A'} | "
                f"Priority: {record.get('final_priority') or 'N/A'} | Status: {record.get('status') or 'N/A'}")

    # Displays facilities-management metrics produced by the Logic Manager.
    def view_facilities_summary(self, summary: FacilitySummaryReport) -> None:
        self.display_message("\n========== FACILITIES SUMMARY REPORT ==========\n"
                             f"Active Hazards: {summary.total_active_hazards}\n"
                             f"Pending Repair: {summary.pending_repair_count}\n"
                             f"In Progress: {summary.in_progress_count}\n"
                             f"Urgent (High/Critical Priority): {summary.urgent_hazard_count}\n"
                             f"Maintenance Backlog Rate: {summary.maintenance_backlog_rate}%")
        for title, counts in (("By Location", summary.hazards_by_location),
                              ("By Category", summary.hazards_by_category)):
            self.display_message(f"\n{title}:")
            if not counts:
                self.display_message("  [Notice] No active hazards.")
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                self.display_message(f"  {name}: {count}")

# # --- Verification / Unit Test Script for Subtask 1.5 ---
# if __name__ == "__main__":
#     # Create mock storage for captured outputs
#     captured_outputs = []

#     def mock_write(msg: str) -> None:
#         captured_outputs.append(msg)

#     def mock_read(prompt: str) -> str:
#         return "mock_input"

#     # Initialize IOManager with injected mocks
#     manager = IOManager(read=mock_read, write=mock_write)

#     # Test base_dir resolution
#     assert isinstance(manager._base_dir, Path)
#     assert manager._base_dir.is_absolute()

#     # Test display_message
#     manager.display_message("System test message initialization successful.")
    
#     print("Verification passed! Captured output:", captured_outputs)

#testing
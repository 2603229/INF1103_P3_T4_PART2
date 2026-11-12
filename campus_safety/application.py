# FILE GUIDE: Application controller that coordinates the four managers.
# IO -> AI -> Logic -> Data for new reports; IO <-> Data/Logic for viewing, search and summaries.
# Managers never call each other directly; this class passes the HazardReport between them.

"""Campus Safety application controller (object-oriented integration layer)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from campus_safety.ai_manager.ai_manager import AIManager
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.ai_manager.gemini_assessor import GeminiAssessor
from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.data_manager.repository_factory import create_repository
from campus_safety.domain.decision import Decision
from campus_safety.domain.facility_summary_report import FacilitySummaryReport
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.io_manager.io_manager import IOManager
from campus_safety.logic_manager.logic_manager import LogicManager

MENU_SUBMIT, MENU_VIEW, MENU_TOP_FIVE, MENU_SEARCH, MENU_SUMMARY, MENU_EXIT = (
    "1", "2", "3", "4", "5", "6")
UNCATEGORISED = "Uncategorised"


# Aggregation: every manager is created outside and injected, so each one can be
# replaced (e.g. by an offline test double) without changing this class.
class CampusSafetyApplication:
    """Coordinate the IO, AI, Logic and Data managers for the CLI workflow."""

    def __init__(self, io: IOManager, ai_manager: AIManager,
                 logic_manager: LogicManager, data_manager: DataManager,
                 base_dir: str | Path | None = None) -> None:
        self._io = io
        self._ai = ai_manager
        self._logic = logic_manager
        self._data = data_manager
        # Image paths from the IO Manager are relative (e.g. "uploads/x.png"); resolve them here.
        self._base_dir = Path(base_dir or Path.cwd()).resolve()

    # ------------------------------------------------------------------
    # Default object graph used by `python main.py`
    # ------------------------------------------------------------------
    @classmethod
    def create_default(cls, project_root: str | Path) -> "CampusSafetyApplication":
        """Load .env, then build the real managers (Gemini + configured JSON/SQLite storage).

        Raises DataStoreError/ValueError if the configured database cannot be opened.
        """
        root = Path(project_root).resolve()
        try:
            from dotenv import load_dotenv
        except ImportError:
            pass  # Environment variables can still be set directly (e.g. docker --env-file).
        else:
            load_dotenv(root / ".env")

        return cls(
            io=IOManager(base_dir=root),
            ai_manager=AIManager(GeminiAssessor()),
            logic_manager=LogicManager(),
            data_manager=DataManager(create_repository()),  # JSON or SQLite from .env
            base_dir=root,
        )

    # ------------------------------------------------------------------
    # Workflow step: AI assessment (AI Manager)
    # ------------------------------------------------------------------
    def assess(self, report: HazardReport) -> None:
        """Attach a validated Gemini assessment; raises AssessmentUnavailable on failure."""
        image_path = str(report.get("image_path") or "")
        if image_path:
            # GeminiAssessor reads visual_evidence_path (never saved), not image_path.
            report.set_runtime_image_path(str((self._base_dir / image_path).resolve()))
        assessment = self._ai.assess(report)
        report.attach_assessment(assessment)

    # ------------------------------------------------------------------
    # Workflow step: priority and routing (Logic Manager)
    # ------------------------------------------------------------------
    def evaluate(self, report: HazardReport) -> Decision:
        """Score the report against stored history and apply the resulting Decision."""
        # The Logic Manager works with plain dictionaries, so convert both sides.
        existing = [stored.as_dict() for stored in self._data.load()]
        record = report.as_dict()

        frequency = self._logic.calculate_historical_frequency(record, existing)
        duplicate = self._logic.check_duplicate(record, existing)

        # Frequency must be in the record BEFORE scoring, or its points are always 0.
        record["historical_frequency"] = frequency
        decision = Decision(**self._logic.evaluate(record))

        report.apply_decision(decision, frequency, duplicate)
        return decision

    # ------------------------------------------------------------------
    # Menu option 1: submit a new report (IO -> AI -> Logic -> Data)
    # ------------------------------------------------------------------
    def submit_report(self) -> HazardReport | None:
        """Run the full workflow; return the saved report, or None if not saved."""
        try:
            report = self._io.get_user_input()
        except InvalidRecord as exc:
            self._io.display_message(f"[Error] Invalid report: {exc}")
            return None

        self._io.display_message("\n[Info] Requesting AI assessment, please wait...")
        try:
            self.assess(report)
        except (AssessmentUnavailable, InvalidRecord) as exc:
            # Business rule: an unassessed report must never be saved.
            self._io.display_message(f"[Error] AI assessment unavailable: {exc}\n"
                                     "[Info] The report was NOT saved. Please try again later.")
            return None

        try:
            decision = self.evaluate(report)
        except DataStoreError as exc:
            self._io.display_message(f"[Error] Cannot read incident history: {exc}")
            return None

        self._io.priority_calculation(report, decision)
        self._io.pre_submission_summary(report)
        if not self._io.confirm():
            self._io.display_message("[Info] Submission cancelled. The report was not saved.")
            return None

        try:
            self._data.save(report)  # The repository assigns the incident ID here.
        except DataStoreError as exc:
            self._io.display_message(f"[Error] Could not save the report: {exc}")
            return None

        self._io.submission_success(report)
        return report

    # ------------------------------------------------------------------
    # Menu option 2: view all incidents (Data -> IO)
    # ------------------------------------------------------------------
    def view_all_reports(self) -> None:
        self._io.view_all_reports(self._data.load())

    # ------------------------------------------------------------------
    # Menu option 3: top hazards (Data -> counting -> IO)
    # ------------------------------------------------------------------
    def top_hazards(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequently reported AI hazard categories, highest first."""
        counts = Counter(
            str(report.get("category") or "").strip() or UNCATEGORISED
            for report in self._data.load()
        )
        return counts.most_common(limit)

    def show_top_hazards(self) -> None:
        self._io.view_frequent_hazards(self.top_hazards())

    # ------------------------------------------------------------------
    # Menu option 4 (new feature): search and filter (IO -> Data -> IO)
    # ------------------------------------------------------------------
    def search_incidents(self) -> list[dict]:
        criteria = self._io.get_search_criteria()
        results = self._data.search(**criteria)
        self._io.view_search_results(results)
        return results

    # ------------------------------------------------------------------
    # Menu option 5 (new feature): facilities summary (Data -> Logic -> IO)
    # ------------------------------------------------------------------
    def facilities_summary(self) -> FacilitySummaryReport:
        records = [report.as_dict() for report in self._data.load()]
        summary = self._logic.generate_facilities_summary(records)
        self._io.view_facilities_summary(summary)
        return summary

    # ------------------------------------------------------------------
    # Main menu loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Show the menu until the user chooses Exit (or presses Ctrl+C)."""
        actions = {
            MENU_SUBMIT: self.submit_report,
            MENU_VIEW: self.view_all_reports,
            MENU_TOP_FIVE: self.show_top_hazards,
            MENU_SEARCH: self.search_incidents,
            MENU_SUMMARY: self.facilities_summary,
        }
        try:
            while True:
                choice = self._io.menu()
                if choice == MENU_EXIT:
                    break
                action = actions.get(choice)
                if action is None:
                    self._io.display_message("[Error] Unknown menu option.")
                    continue
                try:
                    action()
                except DataStoreError as exc:
                    # Storage problems are reported, not shown as a crash/traceback.
                    self._io.display_message(f"[Error] Incident database unavailable: {exc}")
        except (KeyboardInterrupt, EOFError):
            self._io.display_message("")
        self._io.display_message("Exiting Campus Safety Hazard Reporting System. Goodbye!")

# FILE GUIDE: Offline integration tests for CampusSafetyApplication and main.py.
# Uses a scripted fake IO, offline AI providers and a real JSON repository in a
# temporary folder, so the full IO -> AI -> Logic -> Data workflow runs without Gemini.

"""Integration tests for the four-manager application workflow."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from campus_safety.ai_manager.ai_manager import AIManager
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.application import CampusSafetyApplication
from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.data_manager.json_incident_repository import JsonIncidentRepository
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.logic_manager.logic_manager import LogicManager
from tests.ai_manager_test.ai_constant_provider import ConstantProvider
from tests.ai_manager_test.ai_stub_provider import StubProvider

VALID_INPUT = {
    "reporter_name": "Alex Tan",
    "reporter_contact": "alex01@sit.singaporetech.edu.sg",
    "location": "Building E Level 2",
    "impact_headcount": 5,
    "asset_info": "Power socket",
    "description": "Sparks are coming from the wall socket near the desk",
    "image_patch": "",
}


class FakeIO:
    """Scripted stand-in with the same methods the application uses on IOManager."""

    def __init__(self, fields: dict | None = None, confirm: bool = True,
                 menu_choices: tuple[str, ...] = (), criteria: dict | None = None) -> None:
        self._criteria = dict(criteria or {})
        self.search_results = None
        self.summary = None
        self._fields = dict(fields or VALID_INPUT)
        self._confirm = confirm
        self._menu = iter(menu_choices)
        self.messages: list[str] = []
        self.decision = None
        self.success_report = None
        self.viewed_reports = None
        self.top_counts = None

    def menu(self) -> str:
        return next(self._menu)

    def get_user_input(self) -> HazardReport:
        return HazardReport.from_input(self._fields)

    def display_message(self, message: str) -> None:
        self.messages.append(str(message))

    def confirm(self, prompt: str = "") -> bool:
        return self._confirm

    def priority_calculation(self, report, decision) -> None:
        self.decision = decision

    def pre_submission_summary(self, report) -> None:
        pass

    def submission_success(self, report) -> None:
        self.success_report = report

    def view_all_reports(self, reports) -> None:
        self.viewed_reports = reports

    def view_frequent_hazards(self, counts) -> None:
        self.top_counts = counts

    def get_search_criteria(self) -> dict:
        return dict(self._criteria)

    def view_search_results(self, results) -> None:
        self.search_results = results

    def view_facilities_summary(self, summary) -> None:
        self.summary = summary


class BrokenRepository(JsonIncidentRepository):
    """Repository whose reads always fail, to test controlled error handling."""

    def load(self):
        raise DataStoreError("simulated corrupt database")


class ReadOnlyRepository(JsonIncidentRepository):
    """Repository that can be read but refuses to save (e.g. disk full or locked file)."""

    def save(self, report):
        raise DataStoreError("simulated write failure")


class ApplicationWorkflowTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.data = DataManager(JsonIncidentRepository(self.base / "incidents.json"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_app(self, io: FakeIO, provider=None) -> CampusSafetyApplication:
        return CampusSafetyApplication(
            io=io,
            ai_manager=AIManager(provider or ConstantProvider()),
            logic_manager=LogicManager(),
            data_manager=self.data,
            base_dir=self.base,
        )

    # 1. Happy path: report flows through all four managers and is saved.
    def test_submit_saves_assessed_and_prioritised_report(self) -> None:
        io = FakeIO()
        saved = self.make_app(io).submit_report()

        self.assertIsNotNone(saved)
        self.assertEqual(saved.incident_id, "INCIDENT-001")
        stored = self.data.get_by_id("INCIDENT-001")
        self.assertEqual(stored.get("assessment_source"), "Gemini AI")
        self.assertEqual(stored.get("category"), "Electrical")
        self.assertEqual(stored.get("final_priority"), "Normal")  # Medium + Minor = 3 points
        self.assertEqual(stored.get("assigned_route"), "Standard Maintenance Queue")
        self.assertEqual(stored.get("is_duplicate"), "Unique")
        self.assertEqual(stored.status, "Pending Review")
        self.assertIs(io.success_report, saved)

    # 2. Business rule: AI failure means the report is NOT saved.
    def test_ai_failure_does_not_save_report(self) -> None:
        io = FakeIO()
        result = self.make_app(io, StubProvider(AssessmentUnavailable("service down"))).submit_report()

        self.assertIsNone(result)
        self.assertEqual(self.data.load(), [])
        self.assertTrue(any("NOT saved" in m for m in io.messages))

    # 2b. Storage failure while saving is reported instead of crashing.
    def test_save_failure_is_reported_without_crashing(self) -> None:
        self.data = DataManager(ReadOnlyRepository(self.base / "incidents.json"))
        io = FakeIO()

        result = self.make_app(io).submit_report()

        self.assertIsNone(result)
        self.assertIsNone(io.success_report)
        self.assertTrue(any("Could not save" in m for m in io.messages))
        self.assertEqual(self.data.load(), [])

    # 2c. Invalid input stops the workflow before any AI call is made.
    def test_invalid_input_is_rejected_before_ai_call(self) -> None:
        io = FakeIO(dict(VALID_INPUT, reporter_contact="alex@gmail.com"))
        provider = StubProvider(ConstantProvider().assess(HazardReport({})))

        result = self.make_app(io, provider).submit_report()

        self.assertIsNone(result)
        self.assertEqual(provider.received_reports, [])
        self.assertTrue(any("Invalid report" in m for m in io.messages))
        self.assertEqual(self.data.load(), [])

    # 3. Provider returning an unvalidated object is also rejected and not saved.
    def test_invalid_ai_result_does_not_save_report(self) -> None:
        result = self.make_app(FakeIO(), StubProvider({"category": "Electrical"})).submit_report()
        self.assertIsNone(result)
        self.assertEqual(self.data.load(), [])

    # 4. User declines at the confirmation step.
    def test_declined_confirmation_does_not_save(self) -> None:
        io = FakeIO(confirm=False)
        self.assertIsNone(self.make_app(io).submit_report())
        self.assertEqual(self.data.load(), [])
        self.assertTrue(any("cancelled" in m for m in io.messages))

    # 5. Logic integration: frequency is added before scoring, so it affects the score.
    def test_historical_frequency_is_scored(self) -> None:
        app = self.make_app(FakeIO())
        for _ in range(2):
            saved = app.submit_report()
            self.data.update_status(saved.incident_id, "Resolved", "Fixed by maintenance")

        third = app.submit_report()

        self.assertEqual(third.get("historical_frequency"), 2)
        self.assertEqual(app._io.decision.score_breakdown["historical_frequency"], 2)
        self.assertEqual(third.get("priority_score"), 2 + 1 + 2)  # Medium + Minor + freq(2)

    # 6. Logic integration: an open matching incident is flagged as a duplicate.
    def test_open_matching_incident_is_flagged_duplicate(self) -> None:
        app = self.make_app(FakeIO())
        app.submit_report()
        second = app.submit_report()
        self.assertEqual(second.get("is_duplicate"), "Potential Duplicate of INCIDENT-001")

    # 7. Image path from IO is resolved for Gemini but the absolute path is never saved.
    def test_image_path_is_resolved_for_ai_only(self) -> None:
        fields = dict(VALID_INPUT, image_patch="uploads/socket.png")
        provider = StubProvider(ConstantProvider().assess(HazardReport({})))
        self.make_app(FakeIO(fields), provider).submit_report()

        sent = provider.received_reports[0]
        self.assertEqual(sent.get("visual_evidence_path"),
                         str((self.base / "uploads/socket.png").resolve()))
        stored = self.data.get_by_id("INCIDENT-001").as_dict()
        self.assertNotIn("visual_evidence_path", stored)
        self.assertEqual(stored["image_path"], "uploads/socket.png")

    # 8. Top hazards counts categories, highest first, limited to five.
    def test_top_hazards_counts_categories(self) -> None:
        repo = self.data
        categories = ["Electrical"] * 3 + ["Plumbing"] * 2 + ["HVAC", "Structural",
                                                              "IT/Equipment", ""]
        for number, category in enumerate(categories, 1):
            repo.save(HazardReport.from_storage({"incident_id": f"INCIDENT-{number:03d}",
                                                 "category": category}))
        top = self.make_app(FakeIO()).top_hazards()

        self.assertEqual(len(top), 5)
        self.assertEqual(top[0], ("Electrical", 3))
        self.assertEqual(top[1], ("Plumbing", 2))

    def test_top_hazards_empty_database(self) -> None:
        self.assertEqual(self.make_app(FakeIO()).top_hazards(), [])

    # 9. Menu loop dispatches options 2-5, then exits on 6.
    def test_run_dispatches_menu_and_exits(self) -> None:
        io = FakeIO(menu_choices=("2", "3", "4", "5", "6"))
        self.make_app(io).run()
        self.assertEqual(io.viewed_reports, [])
        self.assertEqual(io.top_counts, [])
        self.assertEqual(io.search_results, [])
        self.assertEqual(io.summary.total_active_hazards, 0)
        self.assertTrue(any("Goodbye" in m for m in io.messages))

    def test_run_exits_cleanly_on_ctrl_c(self) -> None:
        io = FakeIO()
        io.menu = lambda: (_ for _ in ()).throw(KeyboardInterrupt)
        self.make_app(io).run()
        self.assertTrue(any("Goodbye" in m for m in io.messages))

    # 11. New feature: search uses IO criteria and DataManager filtering.
    def test_search_incidents_filters_saved_reports(self) -> None:
        app = self.make_app(FakeIO())
        app.submit_report()
        other = dict(VALID_INPUT, location="Library Level 1", asset_info="Ceiling light")
        self.make_app(FakeIO(other)).submit_report()

        io = FakeIO(criteria={"location_query": "library", "status_filter": "",
                              "category_filter": "", "min_severity": 1})
        results = self.make_app(io).search_incidents()

        self.assertEqual([r["incident_id"] for r in results], ["INCIDENT-002"])
        self.assertEqual(io.search_results, results)

    def test_search_severity_threshold_excludes_lower_severity(self) -> None:
        self.make_app(FakeIO()).submit_report()  # ConstantProvider => Medium severity
        io = FakeIO(criteria={"min_severity": 3})  # High and above
        self.assertEqual(self.make_app(io).search_incidents(), [])

    # 12. New feature: summary built by the Logic Manager from saved data.
    def test_facilities_summary_counts_active_incidents(self) -> None:
        app = self.make_app(FakeIO())
        first = app.submit_report()
        app.submit_report()
        third = app.submit_report()
        self.data.update_status(first.incident_id, "In Progress", "Technician assigned")
        self.data.update_status(third.incident_id, "Resolved", "Socket replaced")

        io = FakeIO()
        summary = self.make_app(io).facilities_summary()

        self.assertEqual(summary.total_active_hazards, 2)
        self.assertEqual(summary.pending_repair_count, 1)
        self.assertEqual(summary.in_progress_count, 1)
        self.assertEqual(summary.maintenance_backlog_rate, 50.0)
        self.assertEqual(summary.hazards_by_category, {"Electrical": 2})
        self.assertIs(io.summary, summary)

    # 10. Storage failures during the menu are reported, not raised as a traceback.
    def test_run_reports_storage_error_without_crashing(self) -> None:
        self.data = DataManager(BrokenRepository(self.base / "broken.json"))
        io = FakeIO(menu_choices=("2", "6"))
        self.make_app(io).run()
        self.assertTrue(any("database unavailable" in m for m in io.messages))


class MainEntryPointTests(unittest.TestCase):

    def test_main_returns_error_code_on_storage_startup_failure(self) -> None:
        with patch.object(main.CampusSafetyApplication, "create_default",
                          side_effect=DataStoreError("corrupt")):
            self.assertEqual(main.main(), 1)

    def test_main_returns_error_code_on_bad_backend_setting(self) -> None:
        # patch.dict restores os.environ afterwards; .env never overrides existing variables.
        with patch.dict("os.environ", {"HAZARD_STORAGE_BACKEND": "excel"}):
            self.assertEqual(main.main(), 1)

    def test_main_runs_application_and_exits_cleanly(self) -> None:
        class FakeApp:
            ran = False

            def run(self) -> None:
                FakeApp.ran = True

        with patch.object(main.CampusSafetyApplication, "create_default",
                          return_value=FakeApp()):
            self.assertEqual(main.main(), 0)
        self.assertTrue(FakeApp.ran)

    def test_create_default_builds_real_object_graph(self) -> None:
        with tempfile.TemporaryDirectory() as folder,                 patch.dict("os.environ", {"HAZARD_STORAGE_BACKEND": "json",
                                          "INCIDENTS_DB": str(Path(folder) / "db.json")}):
            app = CampusSafetyApplication.create_default(folder)
            self.assertIsInstance(app, CampusSafetyApplication)
            self.assertEqual(app.top_hazards(), [])


if __name__ == "__main__":
    unittest.main()

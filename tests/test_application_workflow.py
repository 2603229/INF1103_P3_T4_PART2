# FILE GUIDE: Offline integration tests for CampusSafetyApplication and main.py.
# Uses a mocked IOManager, offline AI providers and a real JSON repository in a
# temporary folder, so the full IO -> AI -> Logic -> Data workflow runs without Gemini.

"""Integration tests for the four-manager application workflow."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, create_autospec, patch

import main
from campus_safety.ai_manager.ai_manager import AIManager
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.application import CampusSafetyApplication
from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.data_manager.json_incident_repository import JsonIncidentRepository
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.io_manager.io_manager import IOManager
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


def fake_io(fields: dict | None = None, confirm: bool = True,
            menu_choices: tuple[str, ...] = (), criteria: dict | None = None) -> Mock:
    """Mock IOManager with scripted answers. autospec keeps it in step with the real class."""
    io = create_autospec(IOManager, instance=True)
    io.get_user_input.side_effect = lambda: HazardReport.from_input(dict(fields or VALID_INPUT))
    io.confirm.return_value = confirm
    io.menu.side_effect = list(menu_choices)
    io.get_search_criteria.side_effect = lambda: dict(criteria or {})
    return io


def messages(io: Mock) -> list[str]:
    return [str(call.args[0]) for call in io.display_message.call_args_list]


def shown(method: Mock):
    """The first argument of the most recent call to an IO display method."""
    return method.call_args.args[0]


class ApplicationWorkflowTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.data = DataManager(JsonIncidentRepository(self.base / "incidents.json"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_app(self, io: Mock, provider=None) -> CampusSafetyApplication:
        return CampusSafetyApplication(
            io=io,
            ai_manager=AIManager(provider or ConstantProvider()),
            logic_manager=LogicManager(),
            data_manager=self.data,
            base_dir=self.base,
        )

    def use_failing_repository(self, method: str, message: str) -> None:
        """Swap in a repository whose load() or save() always raises DataStoreError."""
        repository = JsonIncidentRepository(self.base / "failing.json")
        setattr(repository, method, Mock(side_effect=DataStoreError(message)))
        self.data = DataManager(repository)

    # 1. Happy path: report flows through all four managers and is saved.
    def test_submit_saves_assessed_and_prioritised_report(self) -> None:
        io = fake_io()
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
        self.assertIs(shown(io.submission_success), saved)

    # 2. Business rule: AI failure means the report is NOT saved.
    def test_ai_failure_does_not_save_report(self) -> None:
        io = fake_io()
        result = self.make_app(io, StubProvider(AssessmentUnavailable("service down"))).submit_report()

        self.assertIsNone(result)
        self.assertEqual(self.data.load(), [])
        self.assertTrue(any("NOT saved" in m for m in messages(io)))

    # 2b. Storage failure while saving is reported instead of crashing.
    def test_save_failure_is_reported_without_crashing(self) -> None:
        self.use_failing_repository("save", "simulated write failure")
        io = fake_io()

        result = self.make_app(io).submit_report()

        self.assertIsNone(result)
        io.submission_success.assert_not_called()
        self.assertTrue(any("Could not save" in m for m in messages(io)))
        self.assertEqual(self.data.load(), [])

    # 2b-ii. History cannot be read for scoring, so the report is not confirmed or saved.
    def test_history_read_failure_aborts_submission(self) -> None:
        self.use_failing_repository("load", "simulated corrupt database")
        io = fake_io()

        result = self.make_app(io).submit_report()

        self.assertIsNone(result)
        io.priority_calculation.assert_not_called()  # never reached the priority step
        io.submission_success.assert_not_called()
        self.assertTrue(any("Cannot read incident history" in m for m in messages(io)))

    # 2c. Invalid input stops the workflow before any AI call is made.
    def test_invalid_input_is_rejected_before_ai_call(self) -> None:
        io = fake_io(dict(VALID_INPUT, reporter_contact="alex@gmail.com"))
        provider = StubProvider(ConstantProvider().assess(HazardReport({})))

        result = self.make_app(io, provider).submit_report()

        self.assertIsNone(result)
        self.assertEqual(provider.received_reports, [])
        self.assertTrue(any("Invalid report" in m for m in messages(io)))
        self.assertEqual(self.data.load(), [])

    # 3. Provider returning an unvalidated object is also rejected and not saved.
    def test_invalid_ai_result_does_not_save_report(self) -> None:
        result = self.make_app(fake_io(), StubProvider({"category": "Electrical"})).submit_report()
        self.assertIsNone(result)
        self.assertEqual(self.data.load(), [])

    # 4. User declines at the confirmation step.
    def test_declined_confirmation_does_not_save(self) -> None:
        io = fake_io(confirm=False)
        self.assertIsNone(self.make_app(io).submit_report())
        self.assertEqual(self.data.load(), [])
        self.assertTrue(any("cancelled" in m for m in messages(io)))

    # 5. Logic integration: frequency is added before scoring, so it affects the score.
    def test_historical_frequency_is_scored(self) -> None:
        io = fake_io()
        app = self.make_app(io)
        for _ in range(2):
            saved = app.submit_report()
            self.data.update_status(saved.incident_id, "Resolved", "Fixed by maintenance")

        third = app.submit_report()

        decision = io.priority_calculation.call_args.args[1]
        self.assertEqual(third.get("historical_frequency"), 2)
        self.assertEqual(decision.score_breakdown["historical_frequency"], 2)
        self.assertEqual(third.get("priority_score"), 2 + 1 + 2)  # Medium + Minor + freq(2)

    # 6. Logic integration: an open matching incident is flagged as a duplicate.
    def test_open_matching_incident_is_flagged_duplicate(self) -> None:
        app = self.make_app(fake_io())
        app.submit_report()
        second = app.submit_report()
        self.assertEqual(second.get("is_duplicate"), "Potential Duplicate of INCIDENT-001")

    # 7. Image path from IO is resolved for Gemini but the absolute path is never saved.
    def test_image_path_is_resolved_for_ai_only(self) -> None:
        fields = dict(VALID_INPUT, image_patch="uploads/socket.png")
        provider = StubProvider(ConstantProvider().assess(HazardReport({})))
        self.make_app(fake_io(fields), provider).submit_report()

        sent = provider.received_reports[0]
        self.assertEqual(sent.get("visual_evidence_path"),
                         str((self.base / "uploads/socket.png").resolve()))
        stored = self.data.get_by_id("INCIDENT-001").as_dict()
        self.assertNotIn("visual_evidence_path", stored)
        self.assertEqual(stored["image_path"], "uploads/socket.png")

    # 7b. View all passes every stored report to the IO Manager.
    def test_view_all_reports_shows_saved_reports(self) -> None:
        app = self.make_app(fake_io())
        app.submit_report()
        app.submit_report()

        io = fake_io()
        self.make_app(io).view_all_reports()

        self.assertEqual([r.incident_id for r in shown(io.view_all_reports)],
                         ["INCIDENT-001", "INCIDENT-002"])

    # 8. Top hazards counts categories, highest first, limited to five.
    def test_top_hazards_counts_categories(self) -> None:
        categories = ["Electrical"] * 3 + ["Plumbing"] * 2 + ["HVAC", "Structural",
                                                              "IT/Equipment", ""]
        for number, category in enumerate(categories, 1):
            self.data.save(HazardReport.from_storage({"incident_id": f"INCIDENT-{number:03d}",
                                                      "category": category}))
        top = self.make_app(fake_io()).top_hazards()

        self.assertEqual(len(top), 5)
        self.assertEqual(top[0], ("Electrical", 3))
        self.assertEqual(top[1], ("Plumbing", 2))

    def test_top_hazards_groups_missing_categories_and_respects_limit(self) -> None:
        rows = [{"category": "Plumbing"}, {}, {"category": "   "}, {"category": None},
                {"category": "HVAC"}, {"category": "Plumbing"}, {"category": "HVAC"}]
        for number, fields in enumerate(rows, 1):
            self.data.save(HazardReport.from_storage({"incident_id": f"INCIDENT-{number:03d}", **fields}))
        app = self.make_app(fake_io())

        self.assertEqual(app.top_hazards(), [("Uncategorised", 3), ("Plumbing", 2), ("HVAC", 2)])
        # equal counts keep the order they were first reported in
        self.assertEqual(app.top_hazards(limit=2), [("Uncategorised", 3), ("Plumbing", 2)])

    def test_top_hazards_ignores_category_case_and_spacing(self) -> None:
        for number, category in enumerate(["Electrical", "electrical ", "ELECTRICAL", "HVAC"], 1):
            self.data.save(HazardReport.from_storage({"incident_id": f"INCIDENT-{number:03d}",
                                                      "category": category}))
        top = self.make_app(fake_io()).top_hazards()
        self.assertEqual(top, [("Electrical", 3), ("HVAC", 1)])

    def test_top_hazards_rejects_invalid_limit(self) -> None:
        app = self.make_app(fake_io())
        for bad in (0, -3, 2.5, "5", True):
            with self.subTest(limit=bad), self.assertRaises(ValueError):
                app.top_hazards(limit=bad)

    def test_top_hazards_empty_database(self) -> None:
        self.assertEqual(self.make_app(fake_io()).top_hazards(), [])

    # 9. Menu loop dispatches options 2-5, then exits on 6.
    def test_run_dispatches_menu_and_exits(self) -> None:
        io = fake_io(menu_choices=("2", "3", "4", "5", "6"))
        self.make_app(io).run()
        self.assertEqual(shown(io.view_all_reports), [])
        self.assertEqual(shown(io.view_frequent_hazards), [])
        self.assertEqual(shown(io.view_search_results), [])
        self.assertEqual(shown(io.view_facilities_summary).total_active_hazards, 0)
        self.assertTrue(any("Goodbye" in m for m in messages(io)))

    def test_run_exits_cleanly_on_ctrl_c(self) -> None:
        io = fake_io()
        io.menu.side_effect = KeyboardInterrupt
        self.make_app(io).run()
        self.assertTrue(any("Goodbye" in m for m in messages(io)))

    def test_run_exits_cleanly_when_input_ends(self) -> None:
        io = fake_io()
        io.menu.side_effect = EOFError  # piped input reaching end of file
        self.make_app(io).run()
        self.assertTrue(any("Goodbye" in m for m in messages(io)))

    # 11. New feature: search uses IO criteria and DataManager filtering.
    def test_search_incidents_filters_saved_reports(self) -> None:
        self.make_app(fake_io()).submit_report()
        other = dict(VALID_INPUT, location="Library Level 1", asset_info="Ceiling light")
        self.make_app(fake_io(other)).submit_report()

        io = fake_io(criteria={"location_query": "library", "status_filter": "",
                               "category_filter": "", "min_severity": 1})
        results = self.make_app(io).search_incidents()

        self.assertEqual([r["incident_id"] for r in results], ["INCIDENT-002"])
        self.assertEqual(shown(io.view_search_results), results)

    def test_search_severity_threshold_excludes_lower_severity(self) -> None:
        self.make_app(fake_io()).submit_report()  # ConstantProvider => Medium severity
        io = fake_io(criteria={"min_severity": 3})  # High and above
        self.assertEqual(self.make_app(io).search_incidents(), [])

    # 12. New feature: summary built by the Logic Manager from saved data.
    def test_facilities_summary_counts_active_incidents(self) -> None:
        app = self.make_app(fake_io())
        first = app.submit_report()
        app.submit_report()
        third = app.submit_report()
        self.data.update_status(first.incident_id, "In Progress", "Technician assigned")
        self.data.update_status(third.incident_id, "Resolved", "Socket replaced")

        io = fake_io()
        summary = self.make_app(io).facilities_summary()

        self.assertEqual(summary.total_active_hazards, 2)
        self.assertEqual(summary.pending_repair_count, 1)
        self.assertEqual(summary.in_progress_count, 1)
        self.assertEqual(summary.maintenance_backlog_rate, 50.0)
        self.assertEqual(summary.hazards_by_category, {"Electrical": 2})
        self.assertIs(shown(io.view_facilities_summary), summary)

    def test_search_and_summary_handle_empty_database(self) -> None:
        io = fake_io(criteria={"location_query": "library"})
        app = self.make_app(io)

        self.assertEqual(app.search_incidents(), [])
        self.assertEqual(shown(io.view_search_results), [])

        summary = app.facilities_summary()
        self.assertEqual(summary.total_active_hazards, 0)
        self.assertEqual(summary.hazards_by_category, {})
        self.assertIs(shown(io.view_facilities_summary), summary)

    # 10. Storage failures during the menu are reported, not raised as a traceback.
    def test_run_reports_storage_error_without_crashing(self) -> None:
        self.use_failing_repository("load", "simulated corrupt database")
        io = fake_io(menu_choices=("2", "6"))
        self.make_app(io).run()
        self.assertTrue(any("database unavailable" in m for m in messages(io)))

    def test_run_reports_unknown_option_and_keeps_running(self) -> None:
        io = fake_io(menu_choices=("9", "2", "6"))
        self.make_app(io).run()
        self.assertTrue(any("Unknown menu option" in m for m in messages(io)))
        self.assertEqual(shown(io.view_all_reports), [])  # option 2 still ran afterwards
        self.assertTrue(any("Goodbye" in m for m in messages(io)))

    # 13. main.py entry point: exit codes and wiring.
    def test_main_returns_error_code_on_storage_startup_failure(self) -> None:
        with patch.object(main.CampusSafetyApplication, "create_default",
                          side_effect=DataStoreError("corrupt")):
            self.assertEqual(main.main(), 1)

    def test_main_returns_error_code_on_bad_backend_setting(self) -> None:
        # patch.dict restores os.environ afterwards; .env never overrides existing variables.
        with patch.dict("os.environ", {"HAZARD_STORAGE_BACKEND": "excel"}):
            self.assertEqual(main.main(), 1)

    def test_main_returns_interrupted_code_on_ctrl_c_during_startup(self) -> None:
        with patch.object(main.CampusSafetyApplication, "create_default",
                          side_effect=KeyboardInterrupt), \
                patch("sys.stderr"):
            self.assertEqual(main.main(), main.EXIT_INTERRUPTED)

    def test_main_runs_application_and_exits_cleanly(self) -> None:
        app = Mock()
        with patch.object(main.CampusSafetyApplication, "create_default", return_value=app):
            # launch_dashboard=False: don't start Streamlit or open a browser during tests
            self.assertEqual(main.main(launch_dashboard=False), 0)
        app.run.assert_called_once_with()

    def test_create_default_builds_real_object_graph(self) -> None:
        with patch.dict("os.environ", {"HAZARD_STORAGE_BACKEND": "json",
                                       "INCIDENTS_DB": str(self.base / "db.json")}):
            app = CampusSafetyApplication.create_default(self.base)
            self.assertIsInstance(app, CampusSafetyApplication)
            self.assertEqual(app.top_hazards(), [])


if __name__ == "__main__":
    unittest.main()

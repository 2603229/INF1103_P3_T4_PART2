# FILE GUIDE: Offline tests for the Logic Manager's business rules.
# Scoring points, the multi-condition Critical rule, High/Normal escalation,
# routing, historical frequency, duplicate detection, sorting and facilities summary.

"""Business-rule tests for LogicManager and its collaborators."""
import unittest

from campus_safety.logic_manager.logic_manager import LogicManager
from campus_safety.logic_manager.priority_evaluator import PriorityEvaluator
from campus_safety.logic_manager.score_calculator import ScoreCalculator
from campus_safety.logic_manager.text_matcher import TextMatcher


def record(severity="Low", impact="Minor", frequency=0, **extra):
    return {"severity": severity, "operational_impact": impact,
            "historical_frequency": frequency, **extra}


class ScoringTests(unittest.TestCase):

    def setUp(self) -> None:
        self.logic = LogicManager()

    def test_severity_points(self) -> None:
        for severity, points in (("Low", 1), ("Medium", 2), ("High", 4), ("Critical", 5)):
            with self.subTest(severity=severity):
                self.assertEqual(self.logic.calculate_score_breakdown(record(severity))["severity"], points)

    def test_impact_points(self) -> None:
        for impact, points in (("Minor", 1), ("Moderate", 2), ("Severe", 4), ("Catastrophic", 5)):
            with self.subTest(impact=impact):
                breakdown = self.logic.calculate_score_breakdown(record(impact=impact))
                self.assertEqual(breakdown["operational_impact"], points)

    def test_frequency_points_thresholds(self) -> None:
        for frequency, points in ((0, 0), (1, 1), (2, 2), (4, 2), (5, 3), (12, 3)):
            with self.subTest(frequency=frequency):
                breakdown = self.logic.calculate_score_breakdown(record(frequency=frequency))
                self.assertEqual(breakdown["historical_frequency"], points)

    def test_invalid_frequency_scores_zero(self) -> None:
        for bad in ("many", None, -3):
            with self.subTest(value=bad):
                breakdown = self.logic.calculate_score_breakdown(record(frequency=bad))
                self.assertEqual(breakdown["historical_frequency"], 0)

    def test_unknown_label_gets_one_point(self) -> None:
        self.assertEqual(self.logic.calculate_score_breakdown(record("Unknown"))["severity"], 1)

    def test_breakdown_has_one_entry_per_factor(self) -> None:
        self.assertEqual(set(self.logic.calculate_score_breakdown(record())),
                         {"severity", "operational_impact", "historical_frequency"})

    def test_total_score_is_sum_of_breakdown(self) -> None:
        self.assertEqual(self.logic.score(record("High", "Moderate", 2)), 4 + 2 + 2)


class PriorityRuleTests(unittest.TestCase):

    def setUp(self) -> None:
        self.logic = LogicManager()

    def test_critical_requires_both_ai_fields(self) -> None:
        """Multi-condition rule: Critical severity AND Severe/Catastrophic impact."""
        for impact in ("Severe", "Catastrophic"):
            with self.subTest(impact=impact):
                result = self.logic.evaluate(record("Critical", impact))
                self.assertEqual(result["priority"], "Critical")
                self.assertEqual(result["route"], "Urgent Emergency Dispatch")
                self.assertEqual(result["action"], "Immediate Emergency Dispatch")

    def test_critical_severity_with_minor_impact_is_only_high(self) -> None:
        self.assertEqual(self.logic.evaluate(record("Critical", "Minor"))["priority"], "High")

    def test_severe_impact_with_low_severity_is_high(self) -> None:
        result = self.logic.evaluate(record("Low", "Severe"))
        self.assertEqual(result["priority"], "High")
        self.assertEqual(result["route"], "Priority Maintenance Queue")

    def test_score_threshold_escalates_to_high(self) -> None:
        # Medium(2) + Moderate(2) + frequency 5+ (3) = 7 -> High via score threshold
        result = self.logic.evaluate(record("Medium", "Moderate", 5))
        self.assertEqual(result["score"], 7)
        self.assertEqual(result["priority"], "High")

    def test_below_threshold_is_normal(self) -> None:
        result = self.logic.evaluate(record("Medium", "Moderate", 2))  # score 6
        self.assertEqual(result["priority"], "Normal")
        self.assertEqual(result["route"], "Standard Maintenance Queue")
        self.assertEqual(result["action"], "Standard Maintenance")

    def test_labels_are_case_and_space_insensitive(self) -> None:
        self.assertEqual(self.logic.evaluate(record(" critical ", "SEVERE"))["priority"], "Critical")

    def test_evaluate_returns_all_decision_fields(self) -> None:
        self.assertEqual(set(self.logic.evaluate(record())),
                         {"priority", "score", "action", "reason", "route", "score_breakdown"})

    def test_missing_ai_fields_default_to_normal(self) -> None:
        self.assertEqual(self.logic.evaluate({})["priority"], "Normal")


class ConfigurationTests(unittest.TestCase):
    """Collaborators are injected, so behaviour changes without editing any class."""

    def test_custom_high_score_threshold(self) -> None:
        default = LogicManager().evaluate(record("Medium", "Minor"))  # score 3
        lowered = LogicManager(evaluator=PriorityEvaluator(high_score_threshold=3)).evaluate(
            record("Medium", "Minor"))
        self.assertEqual(default["priority"], "Normal")
        self.assertEqual(lowered["priority"], "High")

    def test_custom_calculator_can_be_injected(self) -> None:
        class BigScore(ScoreCalculator):
            def breakdown(self, record):
                return {"severity": 10}

        result = PriorityEvaluator(calculator=BigScore()).evaluate(record("Low", "Minor"))
        self.assertEqual(result["score"], 10)
        self.assertEqual(result["priority"], "High")

    def test_custom_queues_and_default_queue(self) -> None:
        evaluator = PriorityEvaluator(queues={"Critical": "Fire Station"}, default_queue="General Queue")
        self.assertEqual(evaluator.route("critical"), "Fire Station")  # keys are case-insensitive
        self.assertEqual(evaluator.route("  CRITICAL "), "Fire Station")
        self.assertEqual(evaluator.route("Normal"), "General Queue")

    def test_logic_manager_route_uses_record_priority(self) -> None:
        logic = LogicManager()
        self.assertEqual(logic.route({"priority": "High"}), "Priority Maintenance Queue")
        self.assertEqual(logic.route({}), "Standard Maintenance Queue")


class TextMatcherTests(unittest.TestCase):

    def test_tolerates_typos_and_spacing(self) -> None:
        matcher = TextMatcher()
        self.assertTrue(matcher.matches("Libary", "Library"))
        self.assertTrue(matcher.matches("Air con", "Aircon"))

    def test_numbers_must_match_exactly(self) -> None:
        matcher = TextMatcher()
        self.assertFalse(matcher.matches("Lab 1", "Lab 10"))
        self.assertFalse(matcher.matches("Lab 1", "Lab 2"))

    def test_single_letter_identifiers_must_match_exactly(self) -> None:
        self.assertFalse(TextMatcher().matches("Block A Lift 1", "Block B Lift 1"))

    def test_blank_text_never_matches_text(self) -> None:
        self.assertFalse(TextMatcher().matches("", "Library"))

    def test_threshold_property_and_validation(self) -> None:
        matcher = TextMatcher(0.9)
        self.assertEqual(matcher.threshold, 0.9)
        matcher.threshold = 1.0
        self.assertEqual(matcher.threshold, 1.0)
        for bad in (0, -0.1, 1.5):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                matcher.threshold = bad
        with self.assertRaises(ValueError):
            TextMatcher(threshold=0)

    def test_strict_threshold_only_matches_identical_text(self) -> None:
        strict = TextMatcher(1.0)
        self.assertTrue(strict.matches(" Lab  1", "lab 1"))
        self.assertFalse(strict.matches("Libary", "Library"))

    def test_normalise(self) -> None:
        self.assertEqual(TextMatcher.normalise("  Library   Level  2 "), "library level 2")
        self.assertEqual(TextMatcher.normalise(None), "")


class HistoryTests(unittest.TestCase):

    def setUp(self) -> None:
        self.logic = LogicManager()
        self.new = {"location": "Library Level 2", "asset_info": "Ceiling light"}

    def existing(self, ident, status, location="Library Level 2", asset="Ceiling light"):
        return {"incident_id": ident, "status": status, "location": location, "asset_info": asset}

    def test_frequency_counts_only_resolved_or_closed_matches(self) -> None:
        history = [self.existing("INCIDENT-001", "Resolved"),
                   self.existing("INCIDENT-002", "Closed"),
                   self.existing("INCIDENT-003", "Pending Review"),
                   self.existing("INCIDENT-004", "Resolved", location="Block A")]
        self.assertEqual(self.logic.calculate_historical_frequency(self.new, history), 2)

    def test_open_match_is_potential_duplicate(self) -> None:
        history = [self.existing("INCIDENT-001", "Resolved"),
                   self.existing("INCIDENT-007", "In Progress")]
        self.assertEqual(self.logic.check_duplicate(self.new, history),
                         "Potential Duplicate of INCIDENT-007")

    def test_resolved_match_is_not_duplicate(self) -> None:
        self.assertEqual(self.logic.check_duplicate(self.new, [self.existing("INCIDENT-001", "Resolved")]),
                         "Unique")

    def test_missing_fields_never_match(self) -> None:
        history = [self.existing("INCIDENT-001", "Pending Review", location="", asset="")]
        self.assertEqual(self.logic.check_duplicate({"location": "", "asset_info": ""}, history), "Unique")

    def test_blank_record_has_zero_frequency(self) -> None:
        history = [self.existing("INCIDENT-001", "Closed", location="", asset="")]
        self.assertEqual(self.logic.calculate_historical_frequency({"location": "", "asset_info": ""}, history), 0)

    def test_record_is_never_a_duplicate_of_itself(self) -> None:
        saved = self.existing("INCIDENT-009", "Pending Review")
        self.assertEqual(self.logic.check_duplicate(saved, [saved]), "Unique")

    def test_record_is_not_counted_in_its_own_history(self) -> None:
        saved = self.existing("INCIDENT-009", "Closed")
        self.assertEqual(self.logic.calculate_historical_frequency(saved, [saved]), 0)

    def test_fuzzy_matching_tolerates_typos(self) -> None:
        history = [self.existing("INCIDENT-001", "Pending Review", location="Libary Level 2")]
        self.assertEqual(self.logic.check_duplicate(self.new, history), "Potential Duplicate of INCIDENT-001")

    def test_different_block_letters_are_not_duplicates(self) -> None:
        history = [self.existing("INCIDENT-001", "Pending Review", location="Block A Lift 1", asset="Lift")]
        other = {"location": "Block B Lift 1", "asset_info": "Lift"}
        self.assertEqual(self.logic.check_duplicate(other, history), "Unique")

    def test_stricter_matcher_can_be_injected(self) -> None:
        history = [self.existing("INCIDENT-001", "Pending Review", location="Libary Level 2")]
        strict = LogicManager(matcher=TextMatcher(1.0))
        self.assertEqual(strict.check_duplicate(self.new, history), "Unique")

    def test_sort_by_severity(self) -> None:
        rows = [{"severity": s} for s in ("Low", "Critical", "Unknown", "Medium", "High")]
        self.assertEqual([r["severity"] for r in self.logic.sort_incidents_by_severity(rows)],
                         ["Critical", "High", "Medium", "Low", "Unknown"])

    def test_sort_is_case_insensitive_and_does_not_change_input(self) -> None:
        rows = [{"severity": "low"}, {"severity": "CRITICAL"}, {"severity": " high "}]
        result = self.logic.sort_incidents_by_severity(rows)
        self.assertEqual([r["severity"] for r in result], ["CRITICAL", " high ", "low"])
        self.assertEqual([r["severity"] for r in rows], ["low", "CRITICAL", " high "])


class FacilitiesSummaryRuleTests(unittest.TestCase):

    def test_resolved_and_closed_are_excluded(self) -> None:
        rows = [{"status": "Pending Review", "location": "Block A", "category": "HVAC"},
                {"status": "Resolved", "location": "Block A", "category": "HVAC"},
                {"status": "Closed", "location": "Block B", "category": "Plumbing"}]
        summary = LogicManager().generate_facilities_summary(rows)
        self.assertEqual(summary.total_active_hazards, 1)
        self.assertEqual(summary.hazards_by_location, {"Block A": 1})

    def test_pending_and_in_progress_counts(self) -> None:
        rows = [{"status": "Pending Review"}, {"status": "Pending Review"}, {"status": "In Progress"}]
        summary = LogicManager().generate_facilities_summary(rows)
        self.assertEqual((summary.pending_repair_count, summary.in_progress_count), (2, 1))

    def test_urgent_uses_saved_final_priority(self) -> None:
        rows = [{"status": "Pending Review", "final_priority": "Critical"},
                {"status": "In Progress", "final_priority": "High"},
                {"status": "Pending Review", "final_priority": "Normal"}]
        self.assertEqual(LogicManager().generate_facilities_summary(rows).urgent_hazard_count, 2)

    def test_missing_status_and_fields_are_handled(self) -> None:
        summary = LogicManager().generate_facilities_summary([{}])
        self.assertEqual(summary.pending_repair_count, 1)  # legacy rows default to Pending Review
        self.assertEqual(summary.hazards_by_category, {"Unknown": 1})


if __name__ == "__main__":
    unittest.main()
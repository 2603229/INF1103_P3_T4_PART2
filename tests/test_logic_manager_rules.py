# FILE GUIDE: Offline tests for the Logic Manager's business rules.
# Scoring points, the multi-condition Critical rule, High/Normal escalation,
# routing, historical frequency, duplicate detection, sorting and facilities summary.

"""Business-rule tests for LogicManager and its rule/scorer/matcher classes."""
import unittest

from campus_safety.logic_manager.exact_matcher import ExactMatcher
from campus_safety.logic_manager.fuzzy_matcher import FuzzyMatcher
from campus_safety.logic_manager.logic_manager import LogicManager
from campus_safety.logic_manager.priority_evaluator import PriorityEvaluator
from campus_safety.logic_manager.priority_rule import PriorityRule
from campus_safety.logic_manager.router import Router
from campus_safety.logic_manager.scorer import Scorer
from campus_safety.logic_manager.standard_rule import StandardRule
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

    def test_custom_rule_can_be_added_without_editing_evaluator(self) -> None:
        """OCP: new behaviour by adding a PriorityRule subclass."""
        class LargeCrowdRule(PriorityRule):
            def __init__(self) -> None:
                super().__init__("High", "Crowd Control", "Many people affected.")

            def matches(self, severity, operational_impact, score) -> bool:
                return score >= 3

        evaluator = PriorityEvaluator(rules=[LargeCrowdRule(), StandardRule()])
        result = LogicManager(evaluator=evaluator).evaluate(record("Medium", "Minor"))
        self.assertEqual(result["action"], "Crowd Control")

    def test_evaluator_requires_at_least_one_rule(self) -> None:
        with self.assertRaises(ValueError):
            PriorityEvaluator(rules=[])

    def test_router_custom_queue_and_default(self) -> None:
        router = Router({"critical": "Fire Station"}, "General Queue")
        self.assertEqual(router.route("Critical"), "Fire Station")
        self.assertEqual(router.route("Normal"), "General Queue")

    def test_abstract_bases_cannot_be_instantiated(self) -> None:
        for abstract in (PriorityRule, Scorer, TextMatcher):
            with self.subTest(cls=abstract.__name__), self.assertRaises(TypeError):
                abstract()


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

    def test_fuzzy_matching_tolerates_typos(self) -> None:
        history = [self.existing("INCIDENT-001", "Pending Review", location="Libary Level 2")]
        self.assertEqual(self.logic.check_duplicate(self.new, history), "Potential Duplicate of INCIDENT-001")

    def test_fuzzy_matching_requires_same_numbers(self) -> None:
        matcher = FuzzyMatcher()
        self.assertFalse(matcher.matches("Lab 1", "Lab 10"))
        self.assertTrue(matcher.matches("Air con", "Aircon"))

    def test_exact_matcher_can_replace_fuzzy_matcher(self) -> None:
        """LSP: any TextMatcher can be injected."""
        history = [self.existing("INCIDENT-001", "Pending Review", location="Libary Level 2")]
        strict = LogicManager(matcher=ExactMatcher())
        self.assertEqual(strict.check_duplicate(self.new, history), "Unique")

    def test_fuzzy_threshold_validation(self) -> None:
        with self.assertRaises(ValueError):
            FuzzyMatcher(threshold=0)

    def test_sort_by_severity(self) -> None:
        rows = [{"severity": s} for s in ("Low", "Critical", "Unknown", "Medium", "High")]
        self.assertEqual([r["severity"] for r in self.logic.sort_incidents_by_severity(rows)],
                         ["Critical", "High", "Medium", "Low", "Unknown"])


class FacilitiesSummaryRuleTests(unittest.TestCase):

    def test_resolved_and_closed_are_excluded(self) -> None:
        rows = [{"status": "Pending Review", "location": "Block A", "category": "HVAC"},
                {"status": "Resolved", "location": "Block A", "category": "HVAC"},
                {"status": "Closed", "location": "Block B", "category": "Plumbing"}]
        summary = LogicManager().generate_facilities_summary(rows)
        self.assertEqual(summary.total_active_hazards, 1)
        self.assertEqual(summary.hazards_by_location, {"Block A": 1})

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

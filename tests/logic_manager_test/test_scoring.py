import unittest

from campus_safety.logic_manager.frequency_scorer import FrequencyScorer
from campus_safety.logic_manager.impact_scorer import ImpactScorer
from campus_safety.logic_manager.score_calculator import ScoreCalculator
from campus_safety.logic_manager.severity_scorer import SeverityScorer


class SeverityScorerTests(unittest.TestCase):
    def test_known_values(self):
        for value, points in [("Low", 1), ("Medium", 2), ("High", 4), ("Critical", 5)]:
            with self.subTest(value=value):
                self.assertEqual(SeverityScorer().score({"severity": value}), points)

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(SeverityScorer().score({"severity": "  CRITICAL "}), 5)

    def test_missing_field_uses_default_low(self):
        self.assertEqual(SeverityScorer().score({}), 1)

    def test_unknown_value_gets_fallback_points(self):
        self.assertEqual(SeverityScorer().score({"severity": "banana"}), 1)
        self.assertEqual(SeverityScorer().score({"severity": None}), 1)


class ImpactScorerTests(unittest.TestCase):
    def test_known_values(self):
        for value, points in [("Minor", 1), ("Moderate", 2), ("Severe", 4), ("Catastrophic", 5)]:
            with self.subTest(value=value):
                self.assertEqual(ImpactScorer().score({"operational_impact": value}), points)

    def test_missing_and_unknown(self):
        self.assertEqual(ImpactScorer().score({}), 1)
        self.assertEqual(ImpactScorer().score({"operational_impact": "???"}), 1)


class FrequencyScorerTests(unittest.TestCase):
    def test_threshold_boundaries(self):
        cases = {0: 0, 1: 1, 2: 2, 4: 2, 5: 3, 50: 3}
        for freq, points in cases.items():
            with self.subTest(freq=freq):
                self.assertEqual(FrequencyScorer().score({"historical_frequency": freq}), points)

    def test_invalid_input_scores_zero(self):
        for bad in (None, "abc", [], -3):
            with self.subTest(bad=bad):
                self.assertEqual(FrequencyScorer().score({"historical_frequency": bad}), 0)

    def test_numeric_string_accepted(self):
        self.assertEqual(FrequencyScorer().score({"historical_frequency": "5"}), 3)

    def test_missing_field(self):
        self.assertEqual(FrequencyScorer().score({}), 0)


class ScoreCalculatorTests(unittest.TestCase):
    def test_breakdown_keys(self):
        self.assertEqual(
            set(ScoreCalculator().breakdown({})),
            {"severity", "operational_impact", "historical_frequency"},
        )

    def test_total_equals_sum_of_breakdown(self):
        rec = {"severity": "High", "operational_impact": "Moderate", "historical_frequency": 2}
        calc = ScoreCalculator()
        self.assertEqual(calc.breakdown(rec), {"severity": 4, "operational_impact": 2, "historical_frequency": 2})
        self.assertEqual(calc.total(rec), 8)

    def test_maximum_possible_score(self):
        rec = {"severity": "Critical", "operational_impact": "Catastrophic", "historical_frequency": 99}
        self.assertEqual(ScoreCalculator().total(rec), 13)

    def test_empty_record_minimum_score(self):
        self.assertEqual(ScoreCalculator().total({}), 2)


if __name__ == "__main__":
    unittest.main()

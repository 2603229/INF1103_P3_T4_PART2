import unittest

from campus_safety.logic_manager.critical_rule import CriticalRule
from campus_safety.logic_manager.high_rule import HighRule
from campus_safety.logic_manager.standard_rule import StandardRule


class CriticalRuleTests(unittest.TestCase):
    def test_matches_critical_with_severe_or_catastrophic(self):
        for impact in ("severe", "catastrophic"):
            with self.subTest(impact=impact):
                self.assertTrue(CriticalRule().matches("critical", impact, 0))

    def test_critical_with_low_impact_does_not_match(self):
        for impact in ("minor", "moderate"):
            with self.subTest(impact=impact):
                self.assertFalse(CriticalRule().matches("critical", impact, 13))

    def test_severe_impact_without_critical_severity_does_not_match(self):
        self.assertFalse(CriticalRule().matches("high", "catastrophic", 13))

    def test_metadata(self):
        rule = CriticalRule()
        self.assertEqual(rule.priority, "Critical")
        self.assertEqual(rule.action, "Immediate Emergency Dispatch")


class HighRuleTests(unittest.TestCase):
    def test_high_or_critical_severity(self):
        for sev in ("high", "critical"):
            with self.subTest(sev=sev):
                self.assertTrue(HighRule().matches(sev, "minor", 0))

    def test_severe_or_catastrophic_impact(self):
        for impact in ("severe", "catastrophic"):
            with self.subTest(impact=impact):
                self.assertTrue(HighRule().matches("low", impact, 0))

    def test_score_threshold_boundary(self):
        self.assertFalse(HighRule().matches("low", "minor", 6))
        self.assertTrue(HighRule().matches("low", "minor", 7))

    def test_custom_threshold(self):
        self.assertTrue(HighRule(score_threshold=3).matches("low", "minor", 3))
        self.assertFalse(HighRule(score_threshold=10).matches("low", "minor", 9))

    def test_low_everything_does_not_match(self):
        self.assertFalse(HighRule().matches("medium", "moderate", 4))


class StandardRuleTests(unittest.TestCase):
    def test_always_matches(self):
        self.assertTrue(StandardRule().matches("", "", 0))
        self.assertTrue(StandardRule().matches("critical", "catastrophic", 99))

    def test_metadata(self):
        self.assertEqual(StandardRule().priority, "Normal")


if __name__ == "__main__":
    unittest.main()
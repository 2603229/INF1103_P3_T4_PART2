# FILE GUIDE: Offline unit tests for privacy-aware Gemini prompt construction.
# Tests call the extracted helper directly, without invoking the Gemini API.

"""Tests for GeminiPromptBuilder prompt content and identifier redaction."""

import unittest

from campus_safety.ai_manager.gemini_prompt_builder import GeminiPromptBuilder
from campus_safety.domain.hazard_report import HazardReport


class GeminiPromptBuilderTests(unittest.TestCase):
    """Verify prompt formatting and recognition of common personal details."""

    def setUp(self) -> None:
        """Create a report with safe test-only reporter details."""
        self.report = HazardReport({
            "reporter_name": "Private Reporter",
            "reporter_contact": "91234567",
            "location": "Campus Block A",
            "impact_headcount": 3,
            "asset_info": "Electrical outlet",
            "description": "Water leaking near an electrical outlet",
        })

    def test_prompt_includes_hazard_details(self) -> None:
        prompt = GeminiPromptBuilder.build_prompt(self.report)
        self.assertIn("Campus Block A", prompt)
        self.assertIn("Impact Headcount: 3", prompt)
        self.assertIn("Electrical outlet", prompt)
        self.assertIn("Water leaking near an electrical outlet", prompt)

    def test_prompt_requests_exact_five_ai_fields(self) -> None:
        prompt = GeminiPromptBuilder.build_prompt(self.report)
        self.assertIn("containing exactly these five string keys", prompt)
        for field in (
            "risk_summary", "category", "severity",
            "operational_impact", "contextual_insights",
        ):
            with self.subTest(field=field):
                self.assertIn(field, prompt)

    def test_prompt_excludes_reporter_identity_fields(self) -> None:
        prompt = GeminiPromptBuilder.build_prompt(self.report)
        self.assertNotIn("Private Reporter", prompt)
        self.assertNotIn("91234567", prompt)
        self.assertNotIn("Reporter Name:", prompt)
        self.assertNotIn("Reporter Contact:", prompt)

    def test_reporter_name_redaction_is_case_insensitive(self) -> None:
        result = GeminiPromptBuilder.redact_personal_details(
            "PRIVATE REPORTER noticed water near the outlet", self.report
        )
        self.assertNotIn("PRIVATE REPORTER", result)
        self.assertIn("[REDACTED]", result)
        self.assertIn("noticed water near the outlet", result)

    def test_redacts_email_and_phone_from_free_text(self) -> None:
        result = GeminiPromptBuilder.redact_personal_details(
            "Contact sample@example.com or +65 91234567 for this hazard",
            self.report,
        )
        self.assertNotIn("sample@example.com", result)
        self.assertNotIn("91234567", result)
        self.assertIn("[REDACTED EMAIL]", result)
        self.assertIn("for this hazard", result)
    
    def test_redacts_other_singapore_phone_numbers(self) -> None:
        result = GeminiPromptBuilder.redact_personal_details(
            "Contact +65 81234567 about the wet flooring",
            self.report,
        )

        self.assertNotIn("81234567", result)
        self.assertIn("[REDACTED PHONE]", result)
        self.assertIn("wet flooring", result)

    def test_redaction_preserves_safe_hazard_text(self) -> None:
        safe_text = "Wet flooring near staircase B"

        self.assertEqual(
            GeminiPromptBuilder.redact_personal_details(
                safe_text, self.report
            ),
            safe_text,
        )

if __name__ == "__main__":
    unittest.main()
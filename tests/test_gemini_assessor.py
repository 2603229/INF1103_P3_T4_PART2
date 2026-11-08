"""Offline tests for Gemini prompt, strict JSON parsing, and retries."""

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.ai_manager.gemini_assessor import GeminiAssessor
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord


GOOD = {
    "risk_summary": "Water near electrical socket",
    "category": "Electrical",
    "severity": "High",
    "operational_impact": "Moderate",
    "contextual_insights": "Keep people away from the outlet",
}


def fake_sdk(responses):
    """Replace Google SDK with fake modules; no network traffic occurs."""
    client = MagicMock()
    client.__enter__.return_value = client
    client.models.generate_content.side_effect = responses

    fake_types = types.ModuleType("google.genai.types")
    fake_types.HttpOptions = MagicMock(side_effect=lambda **kw: kw)
    fake_types.GenerateContentConfig = MagicMock(side_effect=lambda **kw: kw)

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = MagicMock(return_value=client)
    fake_genai.types = fake_types

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai

    modules = {
        "google": fake_google,
        "google.genai": fake_genai,
        "google.genai.types": fake_types,
    }
    return modules, client


class GeminiAssessorTests(unittest.TestCase):
    def setUp(self):
        self.report = HazardReport({
            "reporter_name": "Private Reporter",
            "reporter_contact": "private@example.com",
            "location": "Campus Block A",
            "impact_headcount": 3,
            "asset_info": "Electrical outlet",
            "description": "Water leaking near an outlet",
        })

    def test_prompt_includes_hazard_but_excludes_identity(self):
        prompt = GeminiAssessor.build_prompt(self.report)
        self.assertIn("Campus Block A", prompt)
        self.assertIn("Water leaking near an outlet", prompt)
        self.assertNotIn("Private Reporter", prompt)
        self.assertNotIn("private@example.com", prompt)

    def test_parse_valid_json(self):
        result = GeminiAssessor.parse_response(json.dumps(GOOD))
        self.assertIsInstance(result, AIAssessment)
        self.assertEqual(result.as_dict(), GOOD)

    def test_parse_markdown_fenced_json(self):
        raw = f"```json\n{json.dumps(GOOD)}\n```"
        self.assertEqual(GeminiAssessor.parse_response(raw).as_dict(), GOOD)

    def test_rejects_malformed_json(self):
        with self.assertRaises(InvalidRecord):
            GeminiAssessor.parse_response("not valid json")

    def test_rejects_empty_response(self):
        with self.assertRaises(InvalidRecord):
            GeminiAssessor.parse_response("  ")

    def test_rejects_extra_json_field(self):
        with self.assertRaises(InvalidRecord):
            GeminiAssessor.parse_response(json.dumps({**GOOD, "extra": "unexpected"}))

    def test_rejects_invalid_severity(self):
        with self.assertRaises(InvalidRecord):
            GeminiAssessor.parse_response(json.dumps({**GOOD, "severity": "Extreme"}))

    def test_missing_api_key_fails_without_calling_sdk(self):
        with self.assertRaises(AssessmentUnavailable):
            GeminiAssessor(api_key="", models=("mock",)).assess(self.report)

    def test_timeout_then_success_retries_offline(self):
        modules, client = fake_sdk([
            TimeoutError("simulated timeout"),
            types.SimpleNamespace(text=json.dumps(GOOD)),
        ])
        with patch.dict(sys.modules, modules), patch(
            "campus_safety.ai_manager.gemini_assessor.time.sleep"
        ) as sleep:
            result = GeminiAssessor(
                api_key="fake-test-key", models=("mock",), max_attempts=2
            ).assess(self.report)
        self.assertEqual(result.as_dict(), GOOD)
        self.assertEqual(client.models.generate_content.call_count, 2)
        sleep.assert_called_once()

    def test_repeated_timeouts_raise_unavailable(self):
        modules, client = fake_sdk([TimeoutError("offline")] * 2)
        with patch.dict(sys.modules, modules), patch(
            "campus_safety.ai_manager.gemini_assessor.time.sleep"
        ):
            with self.assertRaises(AssessmentUnavailable):
                GeminiAssessor(
                    api_key="fake-test-key", models=("mock",), max_attempts=2
                ).assess(self.report)
        self.assertEqual(client.models.generate_content.call_count, 2)

    def test_malformed_json_then_success(self):
        """Verify recovery when the first Gemini response is invalid."""

        modules, client = fake_sdk([
            types.SimpleNamespace(text="{invalid json"),
            types.SimpleNamespace(text=json.dumps(GOOD)),
        ])

        with patch.dict(sys.modules, modules), patch(
            "campus_safety.ai_manager.gemini_assessor.time.sleep"
        ) as sleep:
            result = GeminiAssessor(
                api_key="fake-test-key",
                models=("mock",),
                max_attempts=2,
            ).assess(self.report)

        self.assertIsInstance(result, AIAssessment)
        self.assertEqual(result.as_dict(), GOOD)
        self.assertEqual(client.models.generate_content.call_count, 2)
        sleep.assert_called_once()

    def test_all_models_fail(self):
        """Verify failure handling after exhausting all model retries."""

        modules, client = fake_sdk([
            TimeoutError("offline"),
            TimeoutError("offline"),
            TimeoutError("offline"),
            TimeoutError("offline"),
        ])

        with patch.dict(sys.modules, modules), patch(
            "campus_safety.ai_manager.gemini_assessor.time.sleep"
        ) as sleep:
            with self.assertRaises(AssessmentUnavailable):
                GeminiAssessor(
                    api_key="fake-test-key",
                    models=("model-a", "model-b"),
                    max_attempts=2,
                ).assess(self.report)

        # Two attempts per model, giving four API calls.
        self.assertEqual(client.models.generate_content.call_count, 4)

        # Verify that the second model was attempted.
        tried_models = [
            call.kwargs["model"]
            for call in client.models.generate_content.call_args_list
        ]

        self.assertEqual(
            tried_models,
            ["model-a", "model-a", "model-b", "model-b"],
        )

        # One retry delay for each model.
        self.assertEqual(sleep.call_count, 2)

    def test_unsupported_image_type(self):
        """Verify unsupported attachments are rejected safely."""

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "evidence.txt"
            file_path.write_text("not an image", encoding="utf-8")

            self.report.set_runtime_image_path(str(file_path))

            modules, client = fake_sdk([])

            with patch.dict(sys.modules, modules):
                with self.assertRaisesRegex(
                    AssessmentUnavailable,
                    "unsupported",
                ):
                    GeminiAssessor(
                        api_key="fake-test-key",
                        models=("mock",),
                    ).assess(self.report)

            # The API must not receive the unsupported file.
            client.models.generate_content.assert_not_called()


if __name__ == "__main__":
    unittest.main()

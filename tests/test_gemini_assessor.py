"""Offline tests for Gemini prompt, strict JSON parsing, and retries."""

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import base64
from pathlib import Path

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.ai_manager.gemini_assessor import (
    GeminiAssessor,
    MAX_IMAGE_BYTES,
)
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

    def test_primary_model_fails_fallback_succeeds(self):
        """Use the fallback model when the primary model fails."""

        # Simulate two primary-model failures,
        # followed by a successful fallback-model response.
        modules, client = fake_sdk([
            TimeoutError("primary model attempt 1 failed"),
            TimeoutError("primary model attempt 2 failed"),
            types.SimpleNamespace(text=json.dumps(GOOD)),
        ])

        # Replace the real Gemini SDK and disable retry delays.
        with patch.dict(sys.modules, modules), patch(
            "campus_safety.ai_manager.gemini_assessor.time.sleep"
        ) as sleep:

            result = GeminiAssessor(
                api_key="fake-test-key",
                models=("primary-model", "fallback-model"),
                max_attempts=2,
            ).assess(self.report)

        # The fallback model must return a validated assessment.
        self.assertIsInstance(result, AIAssessment)
        self.assertEqual(result.as_dict(), GOOD)

        # Two failed calls + one successful call = three requests.
        self.assertEqual(
            client.models.generate_content.call_count, 3
        )

        # Verify the exact order in which models were attempted.
        model_calls = [
            call.kwargs["model"]
            for call in client.models.generate_content.call_args_list
        ]

        self.assertEqual(
            model_calls,
            ["primary-model", "primary-model", "fallback-model"],
        )

        # Only one retry delay should occur.
        sleep.assert_called_once()


    def test_valid_image_is_included_in_request(self):
        """Verify Gemini receives the hazard prompt and valid PNG evidence."""

        # Create a small PNG without requiring extra libraries.
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
            "AAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
        )

        # Temporary files are automatically removed after the test.
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "evidence.png"
            image_path.write_bytes(png_bytes)

            # Attach the image to the hazard report.
            self.report.set_runtime_image_path(str(image_path))

            # Simulate a successful Gemini response.
            modules, client = fake_sdk([
                types.SimpleNamespace(text=json.dumps(GOOD)),
            ])

            # Simulate converting image bytes to a Gemini image part.
            fake_types = modules["google.genai.types"]
            fake_types.Part = MagicMock()

            image_part = object()
            fake_types.Part.from_bytes.return_value = image_part

            # Run the assessment without calling the real Gemini API.
            with patch.dict(sys.modules, modules):
                result = GeminiAssessor(
                    api_key="fake-test-key",
                    models=("mock",),
                ).assess(self.report)

            # Check that the correct image bytes and type are used.
            fake_types.Part.from_bytes.assert_called_once_with(
                data=png_bytes,
                mime_type="image/png",
            )

            # Verify Gemini receives exactly one request.
            client.models.generate_content.assert_called_once()

            # Check that the request contains both text and image.
            contents = (
                client.models.generate_content
                .call_args.kwargs["contents"]
            )

            self.assertEqual(len(contents), 2)
            self.assertIn("Campus Block A", contents[0])
            self.assertIs(contents[1], image_part)

            # Verify that the returned assessment is valid.
            self.assertEqual(result.as_dict(), GOOD)


    def test_fake_png_contents_are_rejected(self):
        """Reject a text file disguised as a PNG image."""

        # Create a temporary file with a PNG extension.
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "fake.png"

            # The contents are plain text, not real PNG data.
            file_path.write_text(
                "This is not a PNG image",
                encoding="utf-8",
            )

            # Attach the fake image to the hazard report.
            self.report.set_runtime_image_path(str(file_path))

            # Mock Gemini so no live API calls are made.
            modules, client = fake_sdk([])

            with patch.dict(sys.modules, modules):

                # The invalid image must raise AssessmentUnavailable.
                with self.assertRaises(AssessmentUnavailable):
                    GeminiAssessor(
                        api_key="fake-test-key",
                        models=("mock",),
                    ).assess(self.report)

            # Gemini must never receive the invalid image.
            client.models.generate_content.assert_not_called()


    def test_oversized_image_is_rejected(self):
        """Reject image evidence larger than the 10 MiB limit."""

        # Create a temporary directory for the test file.
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "large.png"

            # Create a file that is one byte larger than the limit.
            # seek() avoids writing 10 MiB of image data manually.
            with file_path.open("wb") as stream:
                stream.seek(MAX_IMAGE_BYTES)
                stream.write(b"0")

            # Attach the oversized file to the hazard report.
            self.report.set_runtime_image_path(str(file_path))

            # Mock Gemini so the test runs offline.
            modules, client = fake_sdk([])

            with patch.dict(sys.modules, modules):

                # The image must be rejected because of its size.
                with self.assertRaisesRegex(
                    AssessmentUnavailable,
                    "size limit",
                ):
                    GeminiAssessor(
                        api_key="fake-test-key",
                        models=("mock",),
                    ).assess(self.report)

            # Verify no Gemini API request was made.
            client.models.generate_content.assert_not_called()

if __name__ == "__main__":
    unittest.main()

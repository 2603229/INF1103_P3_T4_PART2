# FILE GUIDE: Gemini API adapter: sends prompt and validated image evidence,
# parses strict JSON, retries failures and tries configured fallback models.
# Prompt privacy and image validation are delegated to focused helper classes.

"""Gemini provider implementing the AssessmentProvider contract."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import TYPE_CHECKING

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.ai_manager.gemini_prompt_builder import GeminiPromptBuilder
from campus_safety.ai_manager.image_evidence_processor import (
    IMAGE_FORMATS as IMAGE_FORMATS,
    MAX_IMAGE_BYTES as MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS as MAX_IMAGE_PIXELS,
    ImageEvidenceProcessor,
)
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord

if TYPE_CHECKING:
    from google.genai.types import Part

log = logging.getLogger(__name__)

# Re-export image constants so older tests/imports remain compatible.


class GeminiAssessor(AssessmentProvider):
    """Obtain verified, five-field assessments from the live Gemini API.

    Uses GeminiPromptBuilder and ImageEvidenceProcessor to keep prompt privacy
    and image validation separate from API communication.
    """

    def __init__(
        self,
        api_key: str | None = None,
        models: tuple[str, ...] | None = None,
        max_attempts: int = 2,
    ) -> None:
        """Configure credentials, model fallback order, and retry attempts.

        Args:
            api_key: Gemini API key, or GEMINI_API_KEY if omitted.
            models: Ordered model names, or GEMINI_MODELS if omitted.
            max_attempts: Number of attempts per model (at least one).
        """
        self._api_key = api_key if api_key is not None else os.getenv(
            "GEMINI_API_KEY", ""
        )
        self._models = models or tuple(
            value.strip()
            for value in os.getenv(
                "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.6-flash"
            ).split(",")
            if value.strip()
        )
        self._max_attempts = max(1, max_attempts)

    # Preserve the original public/static helpers for existing callers/tests.
    @staticmethod
    def _redact_personal_details(value: object, report: HazardReport) -> str:
        """Delegate free-text redaction to GeminiPromptBuilder."""
        return GeminiPromptBuilder.redact_personal_details(value, report)

    @staticmethod
    def build_prompt(report: HazardReport) -> str:
        """Build the privacy-aware five-field assessment prompt."""
        return GeminiPromptBuilder.build_prompt(report)

    @staticmethod
    def parse_response(raw: str) -> AIAssessment:
        """Decode Gemini JSON into a validated five-field assessment.

        Args:
            raw: Response text, possibly wrapped in Markdown code fences.

        Returns:
            AIAssessment: Validated five-field AI assessment.

        Raises:
            InvalidRecord: If response JSON is empty, malformed or invalid.
        """
        if not isinstance(raw, str) or not raw.strip():
            raise InvalidRecord("Empty AI response")

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

        try:
            payload = json.loads(cleaned.strip())
        except (TypeError, json.JSONDecodeError) as exc:
            raise InvalidRecord("Malformed AI JSON") from exc

        return AIAssessment.from_mapping(payload)

    @staticmethod
    def _image_part(path: str) -> Part:
        """Delegate file validation and SDK part creation to ImageEvidenceProcessor."""
        return ImageEvidenceProcessor.image_part(path)

    def assess(self, report: HazardReport) -> AIAssessment:
        """Call Gemini with bounded retries and return only validated results.

        Args:
            report: Validated hazard report with optional image evidence.

        Returns:
            AIAssessment: Verified five-field assessment.

        Raises:
            AssessmentUnavailable: If credentials, SDK, image evidence,
                API attempts or response validation fail.

        No placeholder assessment is created when the API is unavailable.
        """
        if not self._api_key:
            raise AssessmentUnavailable("GEMINI_API_KEY is not configured")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AssessmentUnavailable("Install google-genai to use Gemini") from exc

        # Always include the text prompt; attach verified image evidence if present.
        contents = [self.build_prompt(report)]
        image_path = str(report.get("visual_evidence_path") or "")
        if image_path:
            try:
                contents.append(self._image_part(image_path))
            except (OSError, ValueError) as exc:
                raise AssessmentUnavailable(
                    "Image evidence could not be read"
                ) from exc

        try:
            with genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=60_000),
            ) as client:
                for model in self._models:
                    for attempt in range(self._max_attempts):
                        try:
                            response = client.models.generate_content(
                                model=model,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json"
                                ),
                            )
                            return self.parse_response(response.text or "")
                        except Exception as exc:
                            # Never accept invalid JSON or failed API calls as success.
                            log.warning(
                                "AI attempt %d for %s failed: %s",
                                attempt + 1,
                                model,
                                exc,
                            )
                            if attempt + 1 < self._max_attempts:
                                time.sleep(1)
        except Exception as exc:
            raise AssessmentUnavailable("Gemini connection unavailable") from exc

        raise AssessmentUnavailable("Gemini did not return a valid assessment")
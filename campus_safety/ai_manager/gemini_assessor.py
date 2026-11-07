# FILE GUIDE: Concrete Gemini assessment provider: builds a privacy-aware prompt, sends an API request,
# parses strict JSON, validates the result and retries failures without inventing a fallback assessment.

"""Gemini AI provider: live API call, prompt, JSON parsing and schema checks."""
from __future__ import annotations
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import TYPE_CHECKING
import time

if TYPE_CHECKING:
    from google.genai.types import Part
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable

log = logging.getLogger(__name__)


# Live Google Gemini adapter implementing AssessmentProvider.
# It handles prompt construction, optional image parts, strict parsing and bounded retries.
class GeminiAssessor(AssessmentProvider):
    """Concrete AI provider using the same five-field Gemini schema as Phase 1."""

    # Read credentials/model preferences from explicit arguments or environment variables.
    # Bound the per-model retry count to avoid an unbounded network loop.
    def __init__(self, api_key: str | None = None,
                 models: tuple[str, ...] | None = None,
                 max_attempts: int = 2) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        self._models = models or tuple(x.strip() for x in
                            os.getenv("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.6-flash").split(",") if x.strip())
        self._max_attempts = max(1, max_attempts)

    # Send hazard details and allowed JSON schema to Gemini, deliberately excluding reporter identity.
    @staticmethod
    def build_prompt(report: HazardReport) -> str:
        # Reporter identity is intentionally excluded, as in Phase 1.
        return ("Analyze this campus safety hazard. Respond with ONLY a JSON object "
                "containing exactly these five string keys: risk_summary, category, "
                "severity, operational_impact, contextual_insights. "
                "category: Electrical, Plumbing, Structural, HVAC, IT/Equipment; "
                "severity: Low, Medium, High, Critical; operational_impact: "
                "Minor, Moderate, Severe, Catastrophic.\n"
                f"Location: {report.location}\n"
                f"Impact Headcount: {report.get('impact_headcount')}\n"
                f"Asset Information: {report.asset_info}\n"
                f"Description: {report.get('description')}")

    # Strip optional Markdown fences, decode JSON and enforce the five-field schema.
    # Raise InvalidRecord rather than guessing at missing or malformed model fields.
    @staticmethod
    def parse_response(raw: str) -> AIAssessment:
        if not isinstance(raw, str) or not raw.strip():
            raise InvalidRecord("Empty AI response")
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"): cleaned = cleaned[:-3]
        try:
            payload = json.loads(cleaned.strip())
        except (TypeError, json.JSONDecodeError) as exc:
            raise InvalidRecord("Malformed AI JSON") from exc
        return AIAssessment.from_mapping(payload)

    # Validate a local image and encode it as an SDK part; import the SDK only when required.
    @staticmethod
    def _image_part(path: str) -> Part:
        """Import the SDK lazily so tests run without Google packages/network."""
        from google.genai import types
        image = Path(path)
        if not image.is_file() or image.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            raise AssessmentUnavailable("Image evidence unavailable or unsupported")
        mime = mimetypes.guess_type(str(image))[0]
        return types.Part.from_bytes(data=image.read_bytes(), mime_type=mime)

    # Call the real Gemini API with strict JSON output and optional image evidence.
    # Try configured models/retries; every unsuccessful path raises AssessmentUnavailable (no fake success).
    def assess(self, report: HazardReport) -> AIAssessment:
        if not self._api_key:
            raise AssessmentUnavailable("GEMINI_API_KEY is not configured")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AssessmentUnavailable("Install google-genai to use Gemini") from exc
        # The text prompt is always included; an optional image becomes a second multimodal part.
        contents = [self.build_prompt(report)]
        image_path = str(report.get("visual_evidence_path") or "")
        if image_path:
            try:
                contents.append(self._image_part(image_path))
            except (OSError, ValueError) as exc:
                raise AssessmentUnavailable("Image evidence could not be read") from exc
        try:
            with genai.Client(api_key=self._api_key,
                              http_options=types.HttpOptions(timeout=60_000)) as client:
                # Move on to another configured model if all attempts for the first fail.
                for model in self._models:
                    for attempt in range(self._max_attempts):
                        try:
                            response = client.models.generate_content(
                                model=model, contents=contents,
                                config=types.GenerateContentConfig(response_mime_type="application/json"))
                            return self.parse_response(response.text or "")
                        except Exception as exc:
                            # Non-matching models, transient network errors and schema errors
                            # never become silently accepted 'offline' assessments.
                            log.warning("AI attempt %d for %s failed: %s", attempt + 1, model, exc)
                            if attempt + 1 < self._max_attempts:
                                time.sleep(1)
        except Exception as exc:
            raise AssessmentUnavailable("Gemini connection unavailable") from exc
        raise AssessmentUnavailable("Gemini did not return a valid assessment")

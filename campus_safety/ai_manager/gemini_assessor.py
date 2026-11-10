# FILE GUIDE: Concrete Gemini assessment provider: builds a privacy-aware prompt, sends an API request,
# parses strict JSON, validates the result and retries failures without inventing a fallback assessment.

"""Gemini AI provider: live API call, prompt, JSON parsing and schema checks."""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from io import BytesIO
from typing import TYPE_CHECKING
import time
import re

if TYPE_CHECKING:
    from google.genai.types import Part
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable

log = logging.getLogger(__name__)


# Image evidence limits and supported formats.
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # Maximum 10 MiB.
MAX_IMAGE_PIXELS = 50_000_000  # Maximum 50 million pixels.

IMAGE_FORMATS = {
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
    ".webp": ("WEBP", "image/webp"),
}


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

    @staticmethod
    def _redact_personal_details(
        value: object,
        report: HazardReport,
    ) -> str:
        """Mask reporter identity, emails and common SG phone numbers."""

        text = str(value or "")

        # Remove the reporter's name and contact if repeated in free text.
        for field in ("reporter_name", "reporter_contact"):
            identifier = str(report.get(field) or "").strip()

            if identifier:
                text = re.sub(
                    rf"(?<!\w){re.escape(identifier)}(?!\w)",
                    "[REDACTED]",
                    text,
                    flags=re.IGNORECASE,
                )

        # Mask email addresses.
        text = re.sub(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            "[REDACTED EMAIL]",
            text,
        )

        # Mask common Singapore phone-number formats.
        text = re.sub(
            r"(?<!\d)(?:\+65[\s-]?)?[689]\d{7}(?!\d)",
            "[REDACTED PHONE]",
            text,
        )

        return text

    # Send hazard details and allowed JSON schema to Gemini, deliberately excluding reporter identity.
    @staticmethod
    def build_prompt(report: HazardReport) -> str:
        """Build Gemini's five-field JSON prompt from a hazard report.

        Args:
            report: Validated campus hazard information.

        Returns:
            str: A structured prompt containing the location, headcount,
                asset information and hazard description.

        Privacy:
            The reporter's name and contact details are excluded.
        """

        # Mask recognizable personal details in free-text fields.
        location = GeminiAssessor._redact_personal_details(
            report.location, report
        )
        asset_info = GeminiAssessor._redact_personal_details(
            report.asset_info, report
        )
        description = GeminiAssessor._redact_personal_details(
            report.get("description"), report
        )
        # Reporter identity is intentionally excluded, as in Phase 1.
        return ("Analyze this campus safety hazard. Respond with ONLY a JSON object "
                "containing exactly these five string keys: risk_summary, category, "
                "severity, operational_impact, contextual_insights. "
                "category: Electrical, Plumbing, Structural, HVAC, IT/Equipment; "
                "severity: Low, Medium, High, Critical; operational_impact: "
                "Minor, Moderate, Severe, Catastrophic.\n"
                f"Location: {location}\n"
                f"Impact Headcount: {report.get('impact_headcount')}\n"
                f"Asset Information: {asset_info}\n"
                f"Description: {description}")

    # Strip optional Markdown fences, decode JSON and enforce the five-field schema.
    # Raise InvalidRecord rather than guessing at missing or malformed model fields.
    @staticmethod
    def parse_response(raw: str) -> AIAssessment:
        """Parse Gemini's JSON response into a validated AI assessment.

        Args:
            raw: Gemini response text, optionally wrapped in Markdown fences.

        Returns:
            AIAssessment: Validated assessment containing five required fields.

        Raises:
            InvalidRecord: If the response is empty, contains malformed JSON,
                or does not satisfy the required assessment schema.
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

    # Validate a local image and encode it as an SDK part; import the SDK only when required.

    @staticmethod
    def _image_part(path: str) -> Part:
        """Validate image evidence and convert it into a Gemini image part.

        Checks that the image exists, has a supported file extension,
        does not exceed the size or resolution limits, and contains
        valid image data matching its extension.

        Args:
            path: Local file path of the image evidence.

        Returns:
            Part: Validated image bytes with the correct MIME type.

        Raises:
            AssessmentUnavailable: If the image is missing, unsupported,
                oversized, corrupted, or cannot be read.
        """
        # Import dependencies only when image evidence is provided.
        try:
            from google.genai import types
            from PIL import Image
        except ImportError as exc:
            raise AssessmentUnavailable(
                "Install google-genai and Pillow to use image evidence"
            ) from exc

        image = Path(path)
        expected = IMAGE_FORMATS.get(image.suffix.lower())

        # Step 1: Check file existence and supported extension.
        if not image.is_file() or expected is None:
            raise AssessmentUnavailable(
                "Image evidence unavailable or unsupported"
            )

        expected_format, mime = expected

        try:
            # Step 2: Check size before reading image into memory.
            byte_count = image.stat().st_size

            if not 0 < byte_count <= MAX_IMAGE_BYTES:
                raise AssessmentUnavailable(
                    "Image evidence is empty or exceeds the 10 MiB size limit"
                )

            data = image.read_bytes()

            if len(data) > MAX_IMAGE_BYTES:
                raise AssessmentUnavailable(
                    "Image evidence exceeds the 10 MiB size limit"
                )

            # Step 3: Verify the actual format, not just the filename.
            with Image.open(BytesIO(data)) as candidate:
                if candidate.format != expected_format:
                    raise AssessmentUnavailable(
                        "Image evidence format does not match the file extension"
                    )

                # Step 4: Reject images with excessive resolution.
                if candidate.width * candidate.height > MAX_IMAGE_PIXELS:
                    raise AssessmentUnavailable(
                        "Image evidence resolution is too large"
                    )

                # Step 5: Verify image file integrity.
                candidate.verify()

            # Step 6: Confirm image data can be decoded.
            with Image.open(BytesIO(data)) as candidate:
                candidate.load()

        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise AssessmentUnavailable(
                "Image evidence is invalid or unreadable"
            ) from exc

        # Step 7: Create the Gemini image part after validation.
        return types.Part.from_bytes(
            data=data,
            mime_type=mime,
        )


    # Call the real Gemini API with strict JSON output and optional image evidence.
    # Try configured models/retries; every unsuccessful path raises AssessmentUnavailable (no fake success).
    def assess(self, report: HazardReport) -> AIAssessment:
        """Request a Gemini assessment with retries and model fallback.

        Args:
            report: Validated hazard report with optional image evidence.

        Returns:
            AIAssessment: A validated AI result containing five fields.

        Raises:
            AssessmentUnavailable: If credentials are missing, image evidence
                is invalid, or all API attempts fail.

        The method never generates a fake assessment on failure.
        """
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

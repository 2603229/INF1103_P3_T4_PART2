# FILE GUIDE: Verify local image evidence and package it for Gemini.
# Reject missing, oversized, corrupted, or incorrectly labeled image files.

"""Image verification and Gemini image-part preparation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable

if TYPE_CHECKING:
    from google.genai.types import Part


MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_IMAGE_PIXELS = 50_000_000  # Maximum decoded pixel count.
IMAGE_FORMATS = {
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
    ".webp": ("WEBP", "image/webp"),
}

class ImageEvidenceProcessor:
    """Validate and prepare image evidence for Gemini API requests.

    Ensures uploaded images meet supported format, size, resolution,
    and integrity requirements before conversion to Gemini SDK parts.

    Keeps image validation separate from GeminiAssessor to support
    the Single Responsibility Principle and independent testing.
    """

    @staticmethod
    def image_part(path: str) -> Part:
        """Validate an image and return its Gemini SDK representation.

        Checks file presence, extension, byte size, actual image format,
        pixel count, and image integrity before packaging the image bytes.

        Args:
            path: Local path to the uploaded image evidence.

        Returns:
            Part: An image part containing verified bytes and MIME type.

        Raises:
            AssessmentUnavailable: If the image is unavailable, unsupported,
                oversized, mislabeled, unreadable, or corrupted.
        """
        # Import optional dependencies only when image evidence is provided.
        try:
            from google.genai import types
            from PIL import Image
        except ImportError as exc:
            raise AssessmentUnavailable(
                "Install google-genai and Pillow to use image evidence"
            ) from exc

        image = Path(path)
        expected = IMAGE_FORMATS.get(image.suffix.lower())

        if not image.is_file() or expected is None:
            raise AssessmentUnavailable("Image evidence unavailable or unsupported")

        expected_format, mime = expected
        try:
            # Reject oversized files before reading image bytes into memory.
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

            # Check content format, pixel count, and file integrity.
            with Image.open(BytesIO(data)) as candidate:
                if candidate.format != expected_format:
                    raise AssessmentUnavailable(
                        "Image evidence format does not match the file extension"
                    )
                if candidate.width * candidate.height > MAX_IMAGE_PIXELS:
                    raise AssessmentUnavailable(
                        "Image evidence resolution is too large"
                    )
                candidate.verify()

            # Decode the pixels separately to catch truncated image content.
            with Image.open(BytesIO(data)) as candidate:
                candidate.load()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise AssessmentUnavailable(
                "Image evidence is invalid or unreadable"
            ) from exc

        return types.Part.from_bytes(data=data, mime_type=mime)
# FILE GUIDE: Offline unit tests for local image validation and Gemini part creation.
# A fake Gemini SDK avoids API calls; Pillow creates small, real test images.

"""Tests for ImageEvidenceProcessor size, format, and integrity checks."""

import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from PIL import Image

from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.ai_manager.image_evidence_processor import ImageEvidenceProcessor


class ImageEvidenceProcessorTests(unittest.TestCase):
    """Validate real local images while replacing Gemini's SDK with a fake."""

    def setUp(self) -> None:
        """Create an isolated test directory and a network-free fake Gemini SDK."""
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.directory = Path(temp_dir.name)

        self.fake_part = object()
        self.from_bytes = MagicMock(return_value=self.fake_part)

        fake_types = types.ModuleType("google.genai.types")
        fake_types.Part = types.SimpleNamespace(from_bytes=self.from_bytes)

        fake_genai = types.ModuleType("google.genai")
        fake_genai.types = fake_types

        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai

        sdk_patch = patch.dict(sys.modules, {
            "google": fake_google,
            "google.genai": fake_genai,
            "google.genai.types": fake_types,
        })
        sdk_patch.start()
        self.addCleanup(sdk_patch.stop)

    def make_image(self, filename: str, image_format: str = "PNG") -> Path:
        """Write a small valid image using the requested encoding."""
        path = self.directory / filename
        with Image.new("RGB", (4, 4), color="red") as image:
            image.save(path, format=image_format)
        return path

    def test_valid_png_creates_gemini_image_part(self) -> None:
        path = self.make_image("evidence.png")
        result = ImageEvidenceProcessor.image_part(str(path))
        self.assertIs(result, self.fake_part)
        self.from_bytes.assert_called_once_with(
            data=path.read_bytes(), mime_type="image/png"
        )

    def test_valid_jpeg_uses_correct_mime_type(self) -> None:
        path = self.make_image("evidence.jpg", "JPEG")
        ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_called_once_with(
            data=path.read_bytes(), mime_type="image/jpeg"
        )

    def test_missing_image_is_rejected(self) -> None:
        with self.assertRaises(AssessmentUnavailable):
            ImageEvidenceProcessor.image_part(str(self.directory / "missing.png"))
        self.from_bytes.assert_not_called()

    def test_empty_image_is_rejected(self) -> None:
        path = self.directory / "empty.png"
        path.write_bytes(b"")
        with self.assertRaises(AssessmentUnavailable):
            ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_not_called()

    def test_unsupported_extension_is_rejected(self) -> None:
        path = self.make_image("evidence.gif", "PNG")
        with self.assertRaises(AssessmentUnavailable):
            ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_not_called()

    def test_corrupt_png_is_rejected(self) -> None:
        path = self.directory / "corrupt.png"
        path.write_bytes(b"not a real PNG file")
        with self.assertRaises(AssessmentUnavailable):
            ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_not_called()

    def test_mismatched_file_extension_is_rejected(self) -> None:
        path = self.make_image("wrong.png", "JPEG")
        with self.assertRaises(AssessmentUnavailable):
            ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_not_called()

    def test_oversized_image_is_rejected(self) -> None:
        path = self.make_image("evidence.png")
        # Lower the size limit in this test instead of allocating a huge file.
        with patch(
            "campus_safety.ai_manager.image_evidence_processor.MAX_IMAGE_BYTES", 10
        ):
            with self.assertRaises(AssessmentUnavailable):
                ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_not_called()

    def test_excessive_pixel_count_is_rejected(self) -> None:
        path = self.make_image("evidence.png")  # Image contains 16 pixels.
        # Lower the pixel limit in this test instead of creating a huge image.
        with patch(
            "campus_safety.ai_manager.image_evidence_processor.MAX_IMAGE_PIXELS", 10
        ):
            with self.assertRaises(AssessmentUnavailable):
                ImageEvidenceProcessor.image_part(str(path))
        self.from_bytes.assert_not_called()


if __name__ == "__main__":
    unittest.main()

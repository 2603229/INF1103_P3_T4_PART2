from __future__ import annotations
from pathlib import Path
import shutil
from typing import Callable

"""Media and file attachment handling for incident evidence."""

class MediaHandler:
    """Manages file dialog selection and safe copying of image evidence into uploads/."""

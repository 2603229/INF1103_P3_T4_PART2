from __future__ import annotations
from pathlib import Path
import shutil
from typing import Callable

"""Media and file attachment handling for incident evidence."""

class MediaHandler:
    """Manages file dialog selection and safe copying of image evidence into uploads/."""

    def __init__(
        self, 
        read: Callable[[str], str] = input,
        write: Callable[[str], None] = print,
        base_dir: str | Path | None = None
    ) -> None:
        """Initialize the MediaHandler with dependency injection for I/O and paths.
        
        Args:
            read: Callable for reading user input (defaults to built-in input).
            write: Callable for displaying messages (defaults to built-in print).
            base_dir: Root directory for the project (defaults to current working directory).
        """
        self._read = read
        self._write = write
        self._base_dir = Path(base_dir or Path.cwd()).resolve()

    def _choose_image_file(self) -> str:
        """Use Phase 1's graphical picker, or ask for a path in headless mode."""
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            pass
        
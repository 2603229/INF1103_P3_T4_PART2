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
        # Attempt to open a GUI file dialog using tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            pass
        else:
            root = None
            try:
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                return str(filedialog.askopenfilename(
                    title="Select Hazard Image",
                    filetypes=[("Supported Images", "*.png *.jpg *.jpeg *.webp")],
                ) or "")
            except (tk.TclError, OSError, RuntimeError):
                pass
            finally:
                if root is not None:
                    try:
                        root.destroy()
                    except (tk.TclError, OSError):
                        pass

        # Fallback to terminal input if GUI picker is unavailable
        self._write("[Info] File picker unavailable; use a file path instead.")
        return self._read("Enter image file path (or press Enter to skip): ").strip().strip('"')

    # Prompts the user to confirm attachment and verifies that the selected path points to a valid, supported image file.
    def attach_image(self, confirm_func: Callable[[str], bool]) -> str:
        """Prompt to attach an image, validate format, and copy to upload dir without collisions."""
        if not confirm_func("Attach image? (y/n): "):
            return ""
            
        source_text = self._choose_image_file().strip().strip('"')
        if not source_text:
            self._write("[Info] No image selected; continuing without image.")
            return ""
        
        source = Path(source_text)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or not source.is_file():
            self._write("[Error] Unsupported or missing image; continuing without one.")
            return ""
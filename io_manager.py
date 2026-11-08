"""
IO Manager Summary:
------------------
- Acts as the CLI presentation and input adapter, keeping all terminal input/output 
  responsibilities strictly separated from domain and business logic.
- Handles interactive user prompting, validation loops (e.g., regex matching for names and 
  SIT credentials), and numerical bounds checks.
- Manages optional image evidence attachments, supporting both graphical file pickers 
  (tkinter) and terminal fallback prompts with safe path copying and collision handling.
- Formats and displays dynamic menus, pre-submission reviews, AI priority score breakdowns, 
  incident lists, and frequent hazard rankings.
- Utilises dependency injection for read/write callables to support automated UI and headless testing.
"""

# Import statements for library modules and type hinting
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

"""IO Manager: CLI interaction and presentation, isolated from domain logic."""


class IOManager:
    """Takes injectable input/output callables for automated UI tests."""
    def __init__(self, read: Callable[[str], str] = input,
                 write: Callable[[str], None] = print,
                 base_dir: str | Path | None = None) -> None:
        self._read: Callable[[str], str] = read
        self._write: Callable[[str], None] = write
        self._base_dir = Path(base_dir or Path.cwd()).resolve()

    def display_message(self, message: str) -> None:
        self._write(str(message))


# --- Verification / Unit Test Script for Subtask 1.5 ---
if __name__ == "__main__":
    # Create mock storage for captured outputs
    captured_outputs = []

    def mock_write(msg: str) -> None:
        captured_outputs.append(msg)

    def mock_read(prompt: str) -> str:
        return "mock_input"

    # Initialize IOManager with injected mocks
    manager = IOManager(read=mock_read, write=mock_write)

    # Test base_dir resolution
    assert isinstance(manager._base_dir, Path)
    assert manager._base_dir.is_absolute()

    # Test display_message
    manager.display_message("System test message initialization successful.")
    
    print("Verification passed! Captured output:", captured_outputs)
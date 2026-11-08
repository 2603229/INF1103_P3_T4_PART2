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
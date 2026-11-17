"""Shared startup configuration for the CLI and the management dashboard.

Both entry points load the same project-local .env and construct their
DataManager through the same repository factory. Existing operating-system
variables take precedence over .env, which is useful for Docker/CI.
"""
from __future__ import annotations

from pathlib import Path

from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.repository_factory import create_repository

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_project_environment(project_root: str | Path = PROJECT_ROOT) -> None:
    """Load optional .env values without overriding environment variables."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # OS environment remains usable if python-dotenv is absent.
    load_dotenv(dotenv_path=Path(project_root).resolve() / ".env", override=False)


def create_data_manager() -> DataManager:
    """Create the configured JSON/SQLite manager shared by both front ends."""
    return DataManager(create_repository())

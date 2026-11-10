# FILE GUIDE: Backend selection factory: chooses JSON (legacy default) or SQLite from explicit configuration.
# Switching storage does not migrate data; migration requires the dedicated utility.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Choose JSON or SQLite without coupling managers/UI to storage details.

The default remains JSON for backwards compatibility. Selection does not
migrate or delete records. Migration is an explicit separate command.
"""
from __future__ import annotations
import os
from pathlib import Path
from campus_safety.data_manager.incident_repository import IncidentRepository
from campus_safety.data_manager.json_incident_repository import JsonIncidentRepository
from campus_safety.data_manager.sqlite_incident_repository import SQLiteIncidentRepository


# Choose the backend from an explicit argument or HAZARD_STORAGE_BACKEND.
# Return the IncidentRepository interface so client code is storage-independent.
def create_repository(backend: str | None = None,
                      path: str | Path | None = None) -> IncidentRepository:
    """Create an implementation using a configured, explicit storage choice.

    The HAZARD_STORAGE_BACKEND environment variable can be ``json`` (default)
    or ``sqlite``. The optional path overrides the selected backend's path.
    INCIDENTS_DB and SQLITE_DB_PATH remain backend-specific and independent.
    """
    choice = os.getenv("HAZARD_STORAGE_BACKEND", "json") if backend is None else backend
    if not isinstance(choice, str):
        raise ValueError("Storage backend must be 'json' or 'sqlite'")
    choice = choice.strip().lower()
    if choice == "json":
        return JsonIncidentRepository(path)
    if choice == "sqlite":
        return SQLiteIncidentRepository(path)
    raise ValueError(f"Unsupported storage backend: {choice!r}; choose 'json' or 'sqlite'")

# FILE GUIDE: Storage-specific exception boundary; protects upper layers from implementation-specific file/SQL errors.
# The CLI and dashboard present this as a controlled failure.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Raised when persistence fails or stored data is corrupt."""


# Storage layer exception that abstracts file/SQLite failure details.
# Callers catch it without depending on a particular repository implementation.
class DataStoreError(RuntimeError):
    """Persistence failed; clients must not treat missing/corrupt data as empty."""

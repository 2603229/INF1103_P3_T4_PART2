# FILE GUIDE: Domain validation exception for user input, AI schema and invalid record transitions.
# Invalid objects should fail before they reach a repository.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Domain/schema validation exception."""


# Used when input or stored data violates domain invariants.
# This is distinct from external AI/network and filesystem errors.
class InvalidRecord(ValueError):
    """Input, schema, or domain invariant was not satisfied."""

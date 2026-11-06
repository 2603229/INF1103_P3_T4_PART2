# FILE GUIDE: Shared field-name and allowed-status constants for records and persistence.
# One canonical definition helps old Phase 1 records round-trip consistently.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Phase 1-compatible storage and AI schema constants (no class declarations)."""

SCHEMA_FIELDS = (
    "incident_id", "timestamp", "status", "reporter_name", "reporter_contact",
    "location", "impact_headcount", "asset_info", "description", "image_path",
    "assessment_source", "category", "severity", "operational_impact",
    "risk_summary", "contextual_insights", "historical_frequency", "is_duplicate",
    "priority_score", "final_priority", "recommended_action",
    "escalation_reason", "assigned_route",
)
VALID_STATUSES = ("Pending Review", "In Progress", "Resolved", "Closed")
VALID_CATEGORIES = ("Electrical", "Plumbing", "Structural", "HVAC", "IT/Equipment")
VALID_SEVERITIES = ("Low", "Medium", "High", "Critical")
VALID_IMPACTS = ("Minor", "Moderate", "Severe", "Catastrophic")
AI_FIELDS = ("risk_summary", "category", "severity", "operational_impact", "contextual_insights")

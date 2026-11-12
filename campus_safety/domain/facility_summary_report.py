from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass(frozen=True)
class FacilitySummaryReport:
    total_active_hazards: int
    pending_repair_count: int
    in_progress_count: int
    urgent_hazard_count: int
    hazards_by_location: Dict[str, int]
    hazards_by_category: Dict[str, int]

    @property
    def maintenance_backlog_rate(self) -> float:
        if self.total_active_hazards == 0:
            return 0.0
        return round((self.pending_repair_count / self.total_active_hazards) * 100, 2)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_active_hazards": self.total_active_hazards,
            "pending_repair_count": self.pending_repair_count,
            "in_progress_count": self.in_progress_count,
            "urgent_hazard_count": self.urgent_hazard_count,
            "maintenance_backlog_rate": self.maintenance_backlog_rate,
            "hazards_by_location": self.hazards_by_location,
            "hazards_by_category": self.hazards_by_category,
        }
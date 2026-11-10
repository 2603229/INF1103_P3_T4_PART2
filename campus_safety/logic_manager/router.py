from typing import Optional


class Router:
    """Maps an evaluated priority to a dispatch queue."""

    _DEFAULT_QUEUES = {
        "critical": "Urgent Emergency Dispatch",
        "high": "Priority Maintenance Queue",
    }
    _DEFAULT_QUEUE = "Standard Maintenance Queue"

    def __init__(
        self,
        queues: Optional[dict[str, str]] = None,
        default_queue: Optional[str] = None,
    ) -> None:
        self._queues = dict(queues) if queues is not None else dict(self._DEFAULT_QUEUES)
        self._default_queue = default_queue or self._DEFAULT_QUEUE

    def route(self, priority: str) -> str:
        return self._queues.get(str(priority).strip().lower(), self._default_queue)

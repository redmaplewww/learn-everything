from __future__ import annotations


class ApprovalGate:
    def __init__(self, approved_actions: set[str] | None = None) -> None:
        self.approved_actions = approved_actions or set()

    def require(self, action_name: str) -> bool:
        return action_name in self.approved_actions

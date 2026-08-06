from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolRequest:
    name: str
    args: dict
    requires_approval: bool = False


class SafeToolServer:
    """A small MCP-like server: list tools, validate requests, execute safely."""

    def __init__(self) -> None:
        self._tools = {
            "read_note": self._read_note,
            "send_email": self._send_email,
        }

    def list_tools(self) -> list[dict]:
        return [
            {"name": "read_note", "risk": "low", "required": ["note_id"]},
            {"name": "send_email", "risk": "high", "required": ["to", "body"]},
        ]

    def call(self, request: ToolRequest, *, approved: bool = False) -> dict:
        if request.name not in self._tools:
            return {"ok": False, "error": f"未知工具：{request.name}"}
        if request.requires_approval and not approved:
            return {"ok": False, "error": "该操作需要人工批准"}
        return {"ok": True, "result": self._tools[request.name](request.args)}

    def _read_note(self, args: dict) -> dict:
        return {"note_id": args["note_id"], "content": "Agent 需要安全边界。"}

    def _send_email(self, args: dict) -> dict:
        return {"sent": True, "to": args["to"], "preview": args["body"][:30]}

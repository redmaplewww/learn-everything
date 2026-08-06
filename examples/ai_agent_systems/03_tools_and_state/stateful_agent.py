from __future__ import annotations

from dataclasses import dataclass, field

from tool_registry import ToolRegistry, build_default_registry


@dataclass
class AgentSession:
    session_id: str
    events: list[str] = field(default_factory=list)

    def add(self, event: str) -> None:
        self.events.append(event)

    def recent_context(self, limit: int = 5) -> str:
        return "\n".join(self.events[-limit:])


class StatefulAgent:
    def __init__(self, tools: ToolRegistry | None = None) -> None:
        self.tools = tools or build_default_registry()

    def answer_with_search(self, session: AgentSession, query: str) -> str:
        session.add(f"user asked: {query}")
        tool_result = self.tools.call("keyword_search", {"query": query})
        session.add(f"tool keyword_search: {tool_result}")
        if not tool_result["ok"]:
            return f"搜索失败：{tool_result['error']}"
        return f"基于最近上下文回答：\n{session.recent_context()}"

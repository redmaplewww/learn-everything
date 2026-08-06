from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


Tool = Callable[[str], str]


@dataclass
class SimpleAgent:
    """A minimal observe-plan-act loop.

    The important difference from a chatbot is that the agent can choose a tool,
    observe the result, and then produce an answer based on that observation.
    """

    tools: dict[str, Tool]
    memory: list[str] = field(default_factory=list)

    def run(self, task: str) -> str:
        self.memory.append(f"user: {task}")
        tool_name = self.plan(task)
        observation = self.act(tool_name, task)
        answer = f"我选择了工具 `{tool_name}`，观察结果是：{observation}"
        self.memory.append(f"assistant: {answer}")
        return answer

    def plan(self, task: str) -> str:
        if "资料" in task or "文档" in task:
            return "search_docs"
        return "summarize"

    def act(self, tool_name: str, task: str) -> str:
        tool = self.tools.get(tool_name)
        if tool is None:
            return f"工具 `{tool_name}` 不存在，无法执行。"
        return tool(task)


def search_docs(query: str) -> str:
    return f"找到与 `{query}` 相关的 2 条资料。"


def summarize(text: str) -> str:
    return f"总结：{text[:40]}"


if __name__ == "__main__":
    agent = SimpleAgent({"search_docs": search_docs, "summarize": summarize})
    print(agent.run("请从资料里找 Agent 的定义"))

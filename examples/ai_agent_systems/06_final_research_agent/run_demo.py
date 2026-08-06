from __future__ import annotations

from research_agent import ResearchAgent


def main() -> None:
    agent = ResearchAgent()
    result = agent.answer("Agent RAG MCP evidence")
    print("问题：", result["question"])
    print("回答：", result["answer"])
    print("引用：")
    for citation in result["citations"]:
        print("-", citation)
    print("审查：", result["review"])
    print("高风险工具调用：", agent.try_high_risk_action("user@example.com", "demo"))


if __name__ == "__main__":
    main()

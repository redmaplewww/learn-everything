from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "examples" / "ai_agent_systems"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.path.insert(0, str(path.parent))
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_simple_agent_uses_tool_and_memory():
    module = load_module(
        "simple_agent", ROOT / "01_agent_vs_chatbot" / "simple_agent.py"
    )
    agent = module.SimpleAgent(
        {"search_docs": module.search_docs, "summarize": module.summarize}
    )

    answer = agent.run("请从资料里找 Agent 的定义")

    assert "search_docs" in answer
    assert len(agent.memory) == 2


def test_tool_registry_validates_missing_args_and_fallback():
    tool_registry = load_module(
        "tool_registry", ROOT / "03_tools_and_state" / "tool_registry.py"
    )
    sys.modules["tool_registry"] = tool_registry
    fallback = load_module(
        "fallback_demo", ROOT / "03_tools_and_state" / "fallback_demo.py"
    )
    registry = tool_registry.build_default_registry()

    missing = registry.call("calculator", {"a": 1})
    fallback_result = fallback.search_with_fallback("Agent")

    assert missing["ok"] is False
    assert fallback_result["used_fallback"] is True
    assert fallback_result["result"]["source"] == "backup"


def test_mini_rag_returns_sources():
    module = load_module("mini_rag", ROOT / "04_rag_memory_evidence" / "mini_rag.py")

    result = module.sample_rag().answer("RAG Agent")

    assert result["sources"]
    assert "资料" in result["answer"]


def test_evidence_log_sufficiency_and_citations():
    module = load_module(
        "evidence_log", ROOT / "04_rag_memory_evidence" / "evidence_log.py"
    )
    log = module.EvidenceLog()
    log.add("D1", "Agent 会调用工具。", "支持 Agent 行动能力", 0.8)

    assert log.is_sufficient()
    assert "D1" in log.as_citations()[0]


def test_safe_tool_server_requires_approval():
    module = load_module(
        "safe_mcp_like_server",
        ROOT / "05_mcp_safe_tools" / "safe_mcp_like_server.py",
    )
    server = module.SafeToolServer()
    request = module.ToolRequest(
        "send_email", {"to": "a@example.com", "body": "hello"}, True
    )

    denied = server.call(request, approved=False)
    allowed = server.call(request, approved=True)

    assert denied["ok"] is False
    assert allowed["ok"] is True


def test_final_research_agent_is_evidence_first():
    for subdir in [
        "04_rag_memory_evidence",
        "05_mcp_safe_tools",
        "06_final_research_agent",
    ]:
        sys.path.insert(0, str(ROOT / subdir))
    try:
        module = load_module(
            "research_agent", ROOT / "06_final_research_agent" / "research_agent.py"
        )
        agent = module.ResearchAgent()

        result = agent.answer("Agent RAG MCP evidence")
        denied = agent.try_high_risk_action("a@example.com", "hello")

        assert result["citations"]
        assert result["review"]["approved"] is True
        assert denied["ok"] is False
    finally:
        for _ in range(3):
            sys.path.pop(0)

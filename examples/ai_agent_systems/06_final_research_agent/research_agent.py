from __future__ import annotations

import sys
from pathlib import Path

EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_ROOT / "04_rag_memory_evidence"))
sys.path.insert(0, str(EXAMPLE_ROOT / "05_mcp_safe_tools"))

from approval_gate import ApprovalGate
from critic_agent import CriticAgent
from evidence_log import EvidenceLog
from mini_rag import MiniRAG, sample_rag
from safe_mcp_like_server import SafeToolServer, ToolRequest


class ResearchAgent:
    """An evidence-first research agent built from the route's core ideas."""

    def __init__(
        self,
        rag: MiniRAG | None = None,
        critic: CriticAgent | None = None,
        approval_gate: ApprovalGate | None = None,
        tools: SafeToolServer | None = None,
    ) -> None:
        self.rag = rag or sample_rag()
        self.critic = critic or CriticAgent()
        self.approval_gate = approval_gate or ApprovalGate()
        self.tools = tools or SafeToolServer()

    def answer(self, question: str) -> dict:
        docs = self.rag.retrieve(question)
        evidence = EvidenceLog()
        for doc in docs:
            evidence.add(
                source_id=doc.doc_id,
                quote=doc.text,
                supports=f"回答问题：{question}",
                confidence=0.8,
            )

        if not evidence.is_sufficient():
            answer = "没有找到足够证据，因此不应该编造结论。"
            citations: list[str] = []
        else:
            citations = evidence.as_citations()
            answer = (
                "基于已检索证据，Agent 系统应该先检索资料、记录证据，"
                "再生成带引用的回答；涉及高风险工具时需要批准。"
            )

        review = self.critic.review(answer, citations)
        return {
            "question": question,
            "answer": answer,
            "citations": citations,
            "review": review,
        }

    def try_high_risk_action(self, to: str, body: str) -> dict:
        request = ToolRequest(
            name="send_email",
            args={"to": to, "body": body},
            requires_approval=True,
        )
        approved = self.approval_gate.require("send_email")
        return self.tools.call(request, approved=approved)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    text: str


class MiniRAG:
    """A tiny keyword retriever for understanding RAG flow."""

    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents

    def retrieve(self, query: str, *, top_k: int = 3) -> list[Document]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, Document]] = []
        for doc in self.documents:
            haystack = f"{doc.title} {doc.text}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def answer(self, query: str) -> dict:
        docs = self.retrieve(query)
        if not docs:
            return {"answer": "没有找到足够证据。", "sources": []}
        titles = "、".join(doc.title for doc in docs)
        return {
            "answer": f"根据 {titles}，可以先基于资料回答，再标注来源。",
            "sources": [doc.doc_id for doc in docs],
        }


def sample_rag() -> MiniRAG:
    return MiniRAG(
        [
            Document("D1", "Agent Loop", "Agent 会观察、规划、调用工具并根据结果继续迭代。"),
            Document("D2", "RAG", "RAG 会先检索资料，再让模型基于证据生成答案。"),
            Document("D3", "MCP", "MCP 用统一协议把安全工具接给 Agent 使用。"),
        ]
    )

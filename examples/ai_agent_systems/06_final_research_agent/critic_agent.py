from __future__ import annotations


class CriticAgent:
    def review(self, answer: str, citations: list[str]) -> dict:
        problems = []
        if not citations:
            problems.append("缺少证据引用")
        if "没有找到足够证据" in answer:
            problems.append("证据不足，不能强行下结论")
        return {
            "approved": not problems,
            "problems": problems,
        }

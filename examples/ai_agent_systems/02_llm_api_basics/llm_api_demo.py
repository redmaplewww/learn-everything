from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, *, temperature: float = 0.2) -> str:
        """Return text generated from a prompt."""


@dataclass
class MockLLMClient:
    """A deterministic stand-in for a real API client.

    Replace this class with OpenAI, Azure, local model, or any other provider
    when you want to connect the example to a real model.
    """

    model: str = "mock-llm"

    def complete(self, prompt: str, *, temperature: float = 0.2) -> str:
        style = "稳定" if temperature <= 0.3 else "发散"
        return f"[{self.model}/{style}] {prompt.strip()[:80]}"


def ask_model(client: LLMClient, question: str) -> str:
    prompt = f"请用一句话回答：{question}"
    return client.complete(prompt, temperature=0.2)


if __name__ == "__main__":
    print(ask_model(MockLLMClient(), "Agent 为什么需要工具？"))

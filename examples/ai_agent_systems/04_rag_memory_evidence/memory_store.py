from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryStore:
    short_term: list[str] = field(default_factory=list)
    long_term: dict[str, str] = field(default_factory=dict)

    def remember_turn(self, text: str, *, window: int = 6) -> None:
        self.short_term.append(text)
        if len(self.short_term) > window:
            self.short_term = self.short_term[-window:]

    def remember_fact(self, key: str, value: str) -> None:
        self.long_term[key] = value

    def context(self) -> str:
        facts = [f"{key}: {value}" for key, value in self.long_term.items()]
        return "\n".join(facts + self.short_term)

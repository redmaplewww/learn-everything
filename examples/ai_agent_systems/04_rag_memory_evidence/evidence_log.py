from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    source_id: str
    quote: str
    supports: str
    confidence: float


@dataclass
class EvidenceLog:
    items: list[Evidence] = field(default_factory=list)

    def add(self, source_id: str, quote: str, supports: str, confidence: float) -> None:
        self.items.append(Evidence(source_id, quote, supports, confidence))

    def is_sufficient(self, *, minimum_items: int = 1, minimum_confidence: float = 0.6) -> bool:
        strong = [item for item in self.items if item.confidence >= minimum_confidence]
        return len(strong) >= minimum_items

    def as_citations(self) -> list[str]:
        return [
            f"[{item.source_id}] {item.quote} -> {item.supports}"
            for item in self.items
        ]

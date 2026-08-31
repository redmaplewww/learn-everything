"""FSRS 复习的客户端无关用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from sqlmodel import Session

from learning_ext.application.projects import _get_project
from learning_ext.db.models import Card
from learning_ext.fsrs_review.service import (
    get_due_cards as get_due_cards_service,
    review_card as review_card_service,
)


@dataclass(frozen=True)
class DueReviewCard:
    id: int
    node_id: int | None
    project_id: int | None
    front: str
    back: str
    card_type: str
    state: int
    reps: int
    next_review: datetime

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DueCards:
    cards: list[DueReviewCard]
    project_id: int | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReviewSubmission:
    card: DueReviewCard
    next_card: DueReviewCard | None

    def to_dict(self) -> dict:
        return asdict(self)


def _due_review_card(card: Card) -> DueReviewCard:
    return DueReviewCard(
        id=card.id,
        node_id=card.node_id,
        project_id=card.project_id,
        front=card.front,
        back=card.back,
        card_type=card.card_type,
        state=card.state,
        reps=card.reps,
        next_review=card.next_review,
    )


def get_due_cards(
    session: Session,
    *,
    project_id: int | None = None,
    limit: int = 100,
    now: datetime | None = None,
    user_id: str = "default",
) -> DueCards:
    """读取当前用户的到期卡片，不改变 FSRS 调度或卡片状态。"""
    if limit < 1:
        raise ValueError("limit 必须大于 0")
    if project_id is not None:
        _get_project(session, project_id, user_id)
    cards = get_due_cards_service(
        session,
        user_id=user_id,
        project_id=project_id,
        now=now,
        limit=limit,
    )
    return DueCards(
        project_id=project_id,
        cards=[_due_review_card(card) for card in cards],
    )


def review_fsrs_card(
    session: Session,
    card_id: int,
    rating: int,
    *,
    project_id: int | None = None,
    user_id: str = "default",
) -> ReviewSubmission:
    """提交一次 FSRS 评分，并读取相同范围内的下一张到期卡片。"""
    card = session.get(Card, card_id)
    if card is None:
        raise ValueError(f"卡片 {card_id} 不存在")
    if card.user_id != user_id:
        raise ValueError(f"卡片 {card_id} 不属于当前用户")
    if project_id is not None:
        _get_project(session, project_id, user_id)
        if card.project_id != project_id:
            raise ValueError(f"卡片 {card_id} 不属于项目 {project_id}")
    reviewed = review_card_service(session, card_id, rating, user_id)
    next_cards = get_due_cards_service(
        session,
        user_id=user_id,
        project_id=project_id,
        limit=1,
    )
    return ReviewSubmission(
        card=_due_review_card(reviewed),
        next_card=_due_review_card(next_cards[0]) if next_cards else None,
    )

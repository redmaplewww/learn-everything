"""复习 HTTP Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCardResponse(BaseModel):
    id: int
    node_id: int | None
    project_id: int | None
    front: str
    back: str
    card_type: str
    state: int
    reps: int
    next_review: datetime


class DueCardsResponse(BaseModel):
    cards: list[ReviewCardResponse]
    project_id: int | None


class ReviewCardRequest(BaseModel):
    rating: int = Field(ge=1, le=4)
    project_id: int | None = None


class ReviewSubmissionResponse(BaseModel):
    card: ReviewCardResponse
    next_card: ReviewCardResponse | None

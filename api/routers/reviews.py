"""FSRS 复习接口。"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from api.dependencies import get_session
from api.schemas.reviews import DueCardsResponse, ReviewCardRequest, ReviewSubmissionResponse
from learning_ext.application import get_due_cards, review_fsrs_card

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/due", response_model=DueCardsResponse)
def read_due_cards(
    project_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return get_due_cards(session, project_id=project_id, limit=limit).to_dict()


@router.post("/{card_id}", response_model=ReviewSubmissionResponse)
def submit_review(
    card_id: int,
    payload: ReviewCardRequest,
    session: Session = Depends(get_session),
):
    return review_fsrs_card(
        session, card_id, payload.rating, project_id=payload.project_id
    ).to_dict()

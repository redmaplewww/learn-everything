"""测验接口。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from api.dependencies import get_session
from api.schemas.quizzes import (
    GenerateQuizRequest,
    QuizAnswerResponse,
    QuizGenerationResponse,
    SubmitQuizAnswerRequest,
)
from learning_ext.application import generate_quiz, submit_quiz_answer

router = APIRouter(prefix="/projects/{project_id}/quizzes", tags=["quizzes"])


@router.post("", response_model=QuizGenerationResponse, status_code=201)
def create_quiz(
    project_id: int,
    payload: GenerateQuizRequest,
    session: Session = Depends(get_session),
):
    return generate_quiz(
        session, project_id, payload.node_ids, count=payload.count, qtype=payload.qtype
    ).to_dict()


@router.post("/questions/{question_id}/answer", response_model=QuizAnswerResponse)
def answer_question(
    project_id: int,
    question_id: int,
    payload: SubmitQuizAnswerRequest,
    session: Session = Depends(get_session),
):
    return submit_quiz_answer(
        session, question_id, payload.answer, project_id=project_id
    ).to_dict()

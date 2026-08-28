"""测验生成的客户端无关用例。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from sqlmodel import Session, select

from learning_ext.application.projects import NodeNotFoundError, _get_project
from learning_ext.db.models import KnowledgeNode, Quiz, QuizQuestion
from learning_ext.quiz.service import (
    generate_quiz as generate_quiz_service,
    grade_answer as grade_answer_service,
)

_QUESTION_TYPES = {"mixed", "choice", "fill", "short", "practice"}


@dataclass(frozen=True)
class QuizQuestionResult:
    id: int
    node_id: int | None
    qtype: str
    stem: str
    options: list[str]
    difficulty: int


@dataclass(frozen=True)
class QuizGeneration:
    quiz_id: int
    project_id: int
    title: str
    quiz_type: str
    questions: list[QuizQuestionResult]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class QuizAnswerSubmission:
    attempt_id: int
    question_id: int
    node_id: int | None
    is_correct: bool
    feedback: str
    mastery: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def generate_quiz(
    session: Session,
    project_id: int,
    node_ids: list[int],
    *,
    count: int = 5,
    qtype: str = "mixed",
    user_id: str = "default",
) -> QuizGeneration:
    """在当前项目的指定节点范围生成并返回测验。"""
    _get_project(session, project_id, user_id)
    if not node_ids:
        raise ValueError("至少选择一个知识点")
    if count < 1 or count > 20:
        raise ValueError("题目数量必须在 1 到 20 之间")
    if qtype not in _QUESTION_TYPES:
        raise ValueError("不支持的题型")
    nodes = [session.get(KnowledgeNode, node_id) for node_id in dict.fromkeys(node_ids)]
    if any(node is None or node.project_id != project_id for node in nodes):
        raise NodeNotFoundError("知识点不存在或不属于当前项目")
    quiz = generate_quiz_service(
        session, user_id, node_ids, project_id=project_id, count=count, qtype=qtype
    )
    questions = list(
        session.exec(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.id)
        ).all()
    )
    return QuizGeneration(
        quiz_id=quiz.id,
        project_id=project_id,
        title=quiz.title,
        quiz_type=quiz.quiz_type,
        questions=[
            QuizQuestionResult(
                id=question.id,
                node_id=question.node_id,
                qtype=question.qtype,
                stem=question.stem,
                options=json.loads(question.options or "[]"),
                difficulty=question.difficulty,
            )
            for question in questions
        ],
    )


def submit_quiz_answer(
    session: Session,
    question_id: int,
    answer: str,
    *,
    project_id: int | None = None,
    user_id: str = "default",
) -> QuizAnswerSubmission:
    """批改单题并返回已持久化反馈及关联节点掌握度。"""
    question = session.get(QuizQuestion, question_id)
    if question is None:
        raise ValueError(f"题目 {question_id} 不存在")
    quiz = session.get(Quiz, question.quiz_id)
    if quiz is None or quiz.user_id != user_id:
        raise ValueError(f"题目 {question_id} 不属于当前用户")
    if project_id is not None and quiz.project_id != project_id:
        raise ValueError(f"题目 {question_id} 不属于项目 {project_id}")
    if not (answer or "").strip():
        raise ValueError("答案不能为空")
    attempt = grade_answer_service(session, question_id, answer, user_id)
    session.expire_all()
    node = session.get(KnowledgeNode, question.node_id) if question.node_id else None
    return QuizAnswerSubmission(
        attempt_id=attempt.id,
        question_id=question_id,
        node_id=question.node_id,
        is_correct=bool(attempt.is_correct),
        feedback=attempt.feedback,
        mastery=node.mastery if node else None,
    )

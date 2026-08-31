"""测验 HTTP Schema。"""

from pydantic import BaseModel, Field


class QuizQuestionResponse(BaseModel):
    id: int
    node_id: int | None
    qtype: str
    stem: str
    options: list[str]
    difficulty: int


class GenerateQuizRequest(BaseModel):
    node_ids: list[int] = Field(min_length=1, max_length=50)
    count: int = Field(default=5, ge=1, le=20)
    qtype: str = Field(default="mixed", pattern="^(mixed|choice|fill|short|practice)$")


class QuizGenerationResponse(BaseModel):
    quiz_id: int
    project_id: int
    title: str
    quiz_type: str
    questions: list[QuizQuestionResponse]


class SubmitQuizAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=20_000)


class QuizAnswerResponse(BaseModel):
    attempt_id: int
    question_id: int
    node_id: int | None
    is_correct: bool
    feedback: str
    mastery: float | None

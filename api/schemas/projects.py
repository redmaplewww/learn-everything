"""项目、路线和工作台 HTTP Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProgressResponse(BaseModel):
    total: int
    done: int
    learning: int
    pending: int
    weak: int = 0
    skipped: int = 0
    pct: float


class ProjectSummaryResponse(BaseModel):
    id: int
    title: str
    topic: str
    status: str
    progress: ProgressResponse
    created_at: datetime


class RoadmapNodeResponse(BaseModel):
    id: int | None
    code: str
    title: str
    description: str
    stage: str
    est_hours: float
    difficulty: int
    prerequisites: list[str]
    mastery: float
    status: str


class ProjectRoadmapResponse(BaseModel):
    project_id: int
    summary: str
    stages: list[dict[str, Any]]
    nodes: list[RoadmapNodeResponse]


class EnvironmentResponse(BaseModel):
    description: str
    status: str


class PracticeResponse(BaseModel):
    id: int | None
    title: str
    description: str
    status: str


class NoteResponse(BaseModel):
    id: int | None
    content: str
    selection: str
    updated_at: datetime


class ResourceResponse(BaseModel):
    id: int | None
    title: str
    url: str
    rtype: str
    description: str
    preview: str
    source: str


class WorkspaceNodeResponse(BaseModel):
    id: int
    code: str
    title: str
    description: str
    stage: str
    status: str
    mastery: float
    est_hours: float
    difficulty: int
    has_content: bool
    learnable: bool
    practice: PracticeResponse | None
    note: NoteResponse | None
    resources: list[ResourceResponse]


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    topic: str
    background: str
    goal: str
    weekly_hours: float
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectWorkspaceResponse(BaseModel):
    project: ProjectResponse
    progress: ProgressResponse
    environment: EnvironmentResponse
    nodes: list[WorkspaceNodeResponse]


class CreateProjectRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    background: str = Field(default="", max_length=4_000)
    goal: str = Field(default="", max_length=4_000)
    weekly_hours: float = Field(gt=0, le=168)
    roadmap: dict[str, Any]


class UpdateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    topic: str = Field(min_length=1, max_length=300)
    background: str = Field(default="", max_length=4_000)
    goal: str = Field(default="", max_length=4_000)
    weekly_hours: float = Field(gt=0, le=168)


class DeleteProjectRequest(BaseModel):
    confirmation_phrase: str = Field(min_length=1, max_length=20)


class ProjectDeletionResponse(BaseModel):
    project_id: int
    deleted: dict[str, int]


class CreateProjectResponse(BaseModel):
    project_id: int
    title: str
    node_count: int
    environment_status: str
    environment_error: str | None


class ContentPreparationRequest(BaseModel):
    initial_count: int = Field(default=3, ge=0, le=3)


class ContentPreparationResponse(BaseModel):
    job_id: int
    project_id: int
    generated_node_ids: list[int]
    failed_node_ids: list[int]
    pending_node_ids: list[int]
    status: str
    attempts: int = 1
    error: str | None = None
    cancel_requested: bool = False

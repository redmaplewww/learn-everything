"""节点状态 HTTP Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.schemas.projects import ProjectWorkspaceResponse


class UpdateNodeStatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=32)


class NodeStatusResponse(BaseModel):
    id: int
    project_id: int
    code: str
    title: str
    description: str
    stage: str
    status: str
    mastery: float
    est_hours: float
    difficulty: int


class UpdateNodeStatusResponse(BaseModel):
    node: NodeStatusResponse
    workspace: ProjectWorkspaceResponse


class NodeDetailResponse(NodeStatusResponse):
    has_content: bool
    practice: dict | None
    note: dict | None
    resources: list[dict]


class GenerateNodeContentRequest(BaseModel):
    force: bool = False


class SaveNodeNoteRequest(BaseModel):
    content: str = Field(max_length=20_000)


class NodeOperationResponse(BaseModel):
    node_id: int
    project_id: int
    status: str
    detail: NodeDetailResponse
    resource_count: int | None = None
    error: str | None = None


class NodeNoteSaveResponse(BaseModel):
    node_id: int
    project_id: int
    note: dict
    detail: NodeDetailResponse

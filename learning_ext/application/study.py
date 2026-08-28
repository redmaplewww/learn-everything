"""节点学习内容的客户端无关用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlmodel import Session

from learning_ext.application.projects import NodeNotFoundError, _get_project, _workspace_node
from learning_ext.db.models import KnowledgeNode
from learning_ext.notes.service import generate_resources, save_note, save_resources_to_db
from learning_ext.progress.study import (
    generate_node_summary_to_db,
    generate_practice_lesson_to_db,
    get_practice_task,
    is_content_valid,
)
from learning_ext.progress.audit import audit_node_content as audit_node_content_service


@dataclass(frozen=True)
class NodeDetail:
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
    has_content: bool
    practice: dict[str, Any] | None
    note: dict[str, Any] | None
    resources: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeContentGeneration:
    node_id: int
    project_id: int
    status: str
    detail: NodeDetail

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PracticeLessonGeneration:
    node_id: int
    project_id: int
    status: str
    detail: NodeDetail

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResourceGeneration:
    node_id: int
    project_id: int
    status: str
    resource_count: int
    error: str | None
    detail: NodeDetail

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeNoteSave:
    node_id: int
    project_id: int
    note: dict[str, Any]
    detail: NodeDetail

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeContentAudit:
    node_id: int
    project_id: int
    report: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_node_detail(
    session: Session, node_id: int, user_id: str = "default"
) -> NodeDetail:
    """读取节点及其已保存学习数据，不生成课程、实操或资料。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    _get_project(session, node.project_id, user_id)
    payload = _workspace_node(session, node, set(), set(), user_id).to_dict()
    payload.pop("learnable")
    return NodeDetail(project_id=node.project_id, **payload)


def generate_node_content(
    session: Session,
    node_id: int,
    *,
    force: bool = False,
    user_id: str = "default",
) -> NodeContentGeneration:
    """显式生成单节点课程，返回生成、跳过或失败的可观察状态。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    project = _get_project(session, node.project_id, user_id)
    if is_content_valid(node.description) and not force:
        return NodeContentGeneration(
            node_id=node_id,
            project_id=node.project_id,
            status="skipped",
            detail=get_node_detail(session, node_id, user_id),
        )
    generated = generate_node_summary_to_db(
        node_id,
        project.topic,
        force=force,
        learning_goal=project.goal or "",
        engine=session.get_bind(),
    )
    session.expire_all()
    return NodeContentGeneration(
        node_id=node_id,
        project_id=node.project_id,
        status="generated" if generated else "failed",
        detail=get_node_detail(session, node_id, user_id),
    )


def generate_practice_lesson(
    session: Session,
    node_id: int,
    *,
    force: bool = False,
    user_id: str = "default",
) -> PracticeLessonGeneration:
    """显式生成节点实操课程，返回任务是否新生成、跳过或失败。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    project = _get_project(session, node.project_id, user_id)
    if get_practice_task(session, node_id) and not force:
        return PracticeLessonGeneration(
            node_id=node_id,
            project_id=node.project_id,
            status="skipped",
            detail=get_node_detail(session, node_id, user_id),
        )
    generated = generate_practice_lesson_to_db(
        node_id,
        project.topic,
        force=force,
        learning_goal=project.goal or "",
        engine=session.get_bind(),
    )
    session.expire_all()
    return PracticeLessonGeneration(
        node_id=node_id,
        project_id=node.project_id,
        status="generated" if generated else "failed",
        detail=get_node_detail(session, node_id, user_id),
    )


def generate_node_resources(
    session: Session, node_id: int, *, user_id: str = "default"
) -> ResourceGeneration:
    """显式生成并替换节点的 AI 资料，不覆盖手工资料。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    project = _get_project(session, node.project_id, user_id)
    try:
        resources = generate_resources(node, project.topic)
        saved = save_resources_to_db(session, node_id, node.project_id, resources)
        session.expire_all()
        return ResourceGeneration(
            node_id=node_id,
            project_id=node.project_id,
            status="generated",
            resource_count=len(saved),
            error=None,
            detail=get_node_detail(session, node_id, user_id),
        )
    except Exception as error:
        session.expire_all()
        detail = get_node_detail(session, node_id, user_id)
        return ResourceGeneration(
            node_id=node_id,
            project_id=node.project_id,
            status="failed",
            resource_count=len(detail.resources),
            error=str(error),
            detail=detail,
        )


def save_node_note(
    session: Session,
    node_id: int,
    content: str,
    *,
    user_id: str = "default",
) -> NodeNoteSave:
    """保存节点笔记并返回当前笔记与节点详情。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    _get_project(session, node.project_id, user_id)
    note = save_note(session, node_id, node.project_id, content, user_id=user_id)
    return NodeNoteSave(
        node_id=node_id,
        project_id=node.project_id,
        note={
            "id": note.id,
            "content": note.content,
            "selection": note.selection,
            "updated_at": note.updated_at,
        },
        detail=get_node_detail(session, node_id, user_id),
    )


def audit_node_content(
    session: Session, node_id: int, *, user_id: str = "default"
) -> NodeContentAudit:
    """只读审计已保存课程内容，不重新生成或修改节点。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    _get_project(session, node.project_id, user_id)
    return NodeContentAudit(
        node_id=node_id,
        project_id=node.project_id,
        report=audit_node_content_service(session, node_id),
    )

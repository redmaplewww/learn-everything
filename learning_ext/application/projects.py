"""项目列表、学习工作台和节点状态用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from learning_ext.db.models import KnowledgeNode, LearningProject, Task
from learning_ext.notes.service import get_note, get_resources
from learning_ext.progress.study import (
    STATUS_MASTERED,
    STATUS_SKIPPED,
    get_next_learnable_nodes,
    get_practice_task,
    get_project_progress,
    is_content_valid,
    set_node_status,
    sort_nodes_by_code,
)
from learning_ext.project_ops import delete_project as delete_project_data


class ApplicationError(ValueError):
    """学习应用用例的可预期业务错误。"""


class ProjectNotFoundError(ApplicationError):
    """项目不存在或不属于当前本地用户。"""


class NodeNotFoundError(ApplicationError):
    """知识点不存在或不属于当前本地用户。"""


@dataclass(frozen=True)
class ProjectSummary:
    id: int
    title: str
    topic: str
    status: str
    progress: dict[str, Any]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkspaceNode:
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
    practice: dict[str, Any] | None
    note: dict[str, Any] | None
    resources: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectWorkspace:
    project: dict[str, Any]
    progress: dict[str, Any]
    environment: dict[str, str]
    nodes: list[WorkspaceNode]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeStatusUpdate:
    node: dict[str, Any]
    workspace: ProjectWorkspace

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_projects(
    session: Session, user_id: str = "default", limit: int = 50
) -> list[ProjectSummary]:
    """返回当前本地用户的项目摘要，按创建时间倒序排列。"""
    if limit <= 0:
        return []
    projects = session.exec(
        select(LearningProject)
        .where(LearningProject.user_id == user_id)
        .order_by(LearningProject.id.desc())
        .limit(limit)
    ).all()
    return [
        ProjectSummary(
            id=_required_id(project.id, "项目"),
            title=project.title,
            topic=project.topic,
            status=project.status,
            progress=get_project_progress(session, _required_id(project.id, "项目")),
            created_at=project.created_at,
        )
        for project in projects
    ]


def get_project_workspace(
    session: Session, project_id: int, user_id: str = "default"
) -> ProjectWorkspace:
    """聚合工作台读取数据，不触发 LLM、网络抓取或后台任务。"""
    project = _get_project(session, project_id, user_id)
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    ordered_nodes = sort_nodes_by_code(list(nodes))
    learnable_ids = {
        node.id
        for node in get_next_learnable_nodes(session, project_id, limit=50)
    }
    done_statuses = {STATUS_MASTERED, STATUS_SKIPPED}

    env_task = session.exec(
        select(Task)
        .where(Task.project_id == project_id)
        .where(Task.task_type == "env")
        .order_by(Task.id.desc())
    ).first()
    environment = {
        "description": env_task.description if env_task else "",
        "status": (
            "done"
            if env_task and env_task.status == "done"
            else "pending"
            if env_task
            else ""
        ),
    }

    workspace_nodes = [
        _workspace_node(session, node, learnable_ids, done_statuses, user_id)
        for node in ordered_nodes
    ]
    project_payload = {
        "id": _required_id(project.id, "项目"),
        "title": project.title,
        "topic": project.topic,
        "background": project.background,
        "goal": project.goal,
        "weekly_hours": project.weekly_hours,
        "status": project.status,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    return ProjectWorkspace(
        project=project_payload,
        progress=get_project_progress(session, project_id),
        environment=environment,
        nodes=workspace_nodes,
    )


def get_project(session: Session, project_id: int, user_id: str = "default") -> dict[str, Any]:
    return _project_payload(_get_project(session, project_id, user_id))


def update_project(
    session: Session,
    project_id: int,
    title: str,
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    user_id: str = "default",
) -> dict[str, Any]:
    """更新项目元信息，不改写已保存的学习路线。"""
    project = _get_project(session, project_id, user_id)
    project.title = _project_text(title, "项目名称", 300)
    project.topic = _project_text(topic, "选题", 300)
    project.background = _optional_project_text(background, "学习背景", 4_000)
    project.goal = _optional_project_text(goal, "学习目标", 4_000)
    project.weekly_hours = _project_hours(weekly_hours)
    project.updated_at = datetime.utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return _project_payload(project)


def delete_project(
    session: Session,
    project_id: int,
    confirmation_phrase: str,
    user_id: str = "default",
) -> dict[str, Any]:
    """确认后级联删除当前用户的项目及其学习数据。"""
    if confirmation_phrase != "DELETE":
        raise ApplicationError("删除项目必须输入 DELETE 确认")
    _get_project(session, project_id, user_id)
    return delete_project_data(session, project_id)


def update_node_status(
    session: Session,
    node_id: int,
    status: str,
    user_id: str = "default",
) -> NodeStatusUpdate:
    """更新节点状态，并返回刷新工作台所需的结构化结果。"""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    _get_project(session, node.project_id, user_id)
    updated = set_node_status(session, node_id, status)
    workspace = get_project_workspace(session, node.project_id, user_id)
    return NodeStatusUpdate(
        node=_node_payload(updated),
        workspace=workspace,
    )


def _get_project(
    session: Session, project_id: int, user_id: str
) -> LearningProject:
    project = session.get(LearningProject, project_id)
    if project is None or project.user_id != user_id:
        raise ProjectNotFoundError(f"项目 {project_id} 不存在")
    return project


def _workspace_node(
    session: Session,
    node: KnowledgeNode,
    learnable_ids: set[int | None],
    done_statuses: set[str],
    user_id: str,
) -> WorkspaceNode:
    node_id = _required_id(node.id, "知识点")
    practice = get_practice_task(session, node_id)
    note = get_note(session, node_id, user_id)
    resources = get_resources(session, node_id)
    return WorkspaceNode(
        id=node_id,
        code=node.code,
        title=node.title,
        description=node.description,
        stage=node.stage,
        status=node.status,
        mastery=node.mastery,
        est_hours=node.est_hours,
        difficulty=node.difficulty,
        has_content=is_content_valid(node.description),
        learnable=node.id in learnable_ids or node.status in done_statuses,
        practice=(
            {
                "id": practice.id,
                "title": practice.title,
                "description": practice.description,
                "status": practice.status,
            }
            if practice
            else None
        ),
        note=(
            {
                "id": note.id,
                "content": note.content,
                "selection": note.selection,
                "updated_at": note.updated_at,
            }
            if note
            else None
        ),
        resources=[
            {
                "id": resource.id,
                "title": resource.title,
                "url": resource.url,
                "rtype": resource.rtype,
                "description": resource.description,
                "preview": resource.preview,
                "source": resource.source,
            }
            for resource in resources
        ],
    )


def _node_payload(node: KnowledgeNode) -> dict[str, Any]:
    return {
        "id": _required_id(node.id, "知识点"),
        "project_id": node.project_id,
        "code": node.code,
        "title": node.title,
        "description": node.description,
        "stage": node.stage,
        "status": node.status,
        "mastery": node.mastery,
        "est_hours": node.est_hours,
        "difficulty": node.difficulty,
    }


def _project_payload(project: LearningProject) -> dict[str, Any]:
    return {
        "id": _required_id(project.id, "项目"),
        "title": project.title,
        "topic": project.topic,
        "background": project.background,
        "goal": project.goal,
        "weekly_hours": project.weekly_hours,
        "status": project.status,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _project_text(value: str, label: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ApplicationError(f"{label}不能为空")
    if len(normalized) > maximum:
        raise ApplicationError(f"{label}不能超过 {maximum} 个字符")
    return normalized


def _optional_project_text(value: str, label: str, maximum: int) -> str:
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ApplicationError(f"{label}不能超过 {maximum} 个字符")
    return normalized


def _project_hours(value: float) -> float:
    if not 0 < value <= 168:
        raise ApplicationError("每周投入时间必须在 0 到 168 小时之间")
    return value


def _required_id(value: int | None, label: str) -> int:
    if value is None:
        raise ApplicationError(f"{label}缺少 ID")
    return value

"""学习路线读取用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import logging

from sqlmodel import Session, select

from learning_ext.application.projects import _get_project
from learning_ext.db.models import KnowledgeNode, LearningProject
from learning_ext.path_generator.service import (
    audit_and_rewrite_roadmap,
    audit_existing_roadmap,
    generate_roadmap,
    load_roadmap,
    refine_roadmap as refine_roadmap_service,
    replace_project_roadmap as replace_project_roadmap_service,
    save_roadmap,
)
from learning_ext.progress.study import generate_env_checklist, save_env_tasks
from learning_ext.observability import current_request_id

logger = logging.getLogger("uvicorn.error")
from learning_ext.application.jobs import ContentPreparation, prepare_project_content


@dataclass(frozen=True)
class ProjectRoadmap:
    project_id: int
    summary: str
    stages: list[dict[str, Any]]
    nodes: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoadmapPreview:
    roadmap: dict[str, Any]
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectCreation:
    project_id: int
    title: str
    node_count: int
    environment_status: str
    environment_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoadmapReplacement:
    project_id: int
    previous_node_count: int
    new_node_count: int
    content_preparation: ContentPreparation

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRoadmapAudit:
    project_id: int
    audit: dict[str, Any]
    proposed_roadmap: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_project_roadmap(
    session: Session, project_id: int, user_id: str = "default"
) -> ProjectRoadmap:
    """读取项目路线并补齐持久化节点 ID。"""
    project = _get_project(session, project_id, user_id)

    roadmap = load_roadmap(session, project_id)
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    id_by_code = {node.code: node.id for node in nodes}
    roadmap_nodes = [
        {**node, "id": id_by_code.get(node.get("code"))}
        for node in roadmap.get("nodes", [])
    ]
    return ProjectRoadmap(
        project_id=project_id,
        summary=roadmap.get("summary", ""),
        stages=list(roadmap.get("stages", [])),
        nodes=roadmap_nodes,
    )


def generate_roadmap_preview(
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    *,
    model_name: str | None = None,
) -> RoadmapPreview:
    """生成并审计路线，不写入数据库。"""
    normalized_topic = _required_text(topic, "选题")
    normalized_hours = _weekly_hours(weekly_hours)
    logger.info(
        "路线预览开始 request_id=%s topic=%s weekly_hours=%s",
        current_request_id(),
        normalized_topic[:120],
        normalized_hours,
    )
    generated = generate_roadmap(
        normalized_topic,
        background or "",
        goal or "",
        normalized_hours,
        model_name=model_name,
    )
    audited = audit_and_rewrite_roadmap(
        generated,
        normalized_topic,
        background or "",
        goal or "",
        normalized_hours,
        model_name=model_name,
    )
    audit = dict(audited.pop("_audit", {}))
    logger.info(
        "路线预览完成 request_id=%s topic=%s node_count=%s audit_score=%s",
        current_request_id(),
        normalized_topic[:120],
        len(audited.get("nodes", [])),
        audit.get("score"),
    )
    return RoadmapPreview(roadmap=audited, audit=audit)


def refine_roadmap_preview(
    roadmap: dict[str, Any],
    instruction: str,
    *,
    model_name: str | None = None,
) -> dict[str, Any]:
    """按用户意见调整未保存的路线。"""
    if not isinstance(roadmap, dict) or not roadmap.get("nodes"):
        raise ValueError("请先生成有效的学习路线")
    logger.info(
        "路线调整开始 request_id=%s node_count=%s instruction_length=%s",
        current_request_id(),
        len(roadmap.get("nodes", [])),
        len(instruction.strip()),
    )
    result = refine_roadmap_service(
        roadmap, _required_text(instruction, "调整意见"), model_name=model_name
    )
    logger.info(
        "路线调整完成 request_id=%s node_count=%s",
        current_request_id(),
        len(result.get("nodes", [])) if isinstance(result, dict) else 0,
    )
    return result


def create_project(
    session: Session,
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    roadmap: dict[str, Any],
    *,
    user_id: str = "default",
    model_name: str | None = None,
) -> ProjectCreation:
    """持久化路线；环境清单失败不回滚已成功创建的项目。"""
    normalized_topic = _required_text(topic, "选题")
    normalized_hours = _weekly_hours(weekly_hours)
    if not isinstance(roadmap, dict) or not roadmap.get("nodes"):
        raise ValueError("请先生成有效的学习路线")
    project = save_roadmap(
        session=session,
        user_id=user_id,
        topic=normalized_topic,
        background=background or "",
        goal=goal or "",
        weekly_hours=normalized_hours,
        roadmap=roadmap,
    )
    logger.info(
        "路线项目保存完成 request_id=%s project_id=%s node_count=%s",
        current_request_id(),
        project.id,
        len(roadmap["nodes"]),
    )
    environment_error = None
    environment_status = "ready"
    try:
        env_markdown = generate_env_checklist(
            normalized_topic, background or "", model_name=model_name
        )
        save_env_tasks(session, project.id, env_markdown)
    except Exception as error:
        environment_status = "failed"
        environment_error = str(error)
    return ProjectCreation(
        project_id=project.id,
        title=project.title,
        node_count=len(roadmap["nodes"]),
        environment_status=environment_status,
        environment_error=environment_error,
    )


def replace_project_roadmap(
    session: Session,
    project_id: int,
    roadmap: dict[str, Any],
    *,
    confirmed: bool,
    user_id: str = "default",
) -> RoadmapReplacement:
    """确认后替换项目路线和关联学习数据，并启动内容准备。"""
    _get_project(session, project_id, user_id)
    if not confirmed:
        raise ValueError("替换路线会清除现有节点、笔记、资料、复习和测验数据，必须明确确认")
    if not isinstance(roadmap, dict) or not roadmap.get("nodes"):
        raise ValueError("替换路线必须包含至少一个节点")
    logger.info(
        "路线替换开始 request_id=%s project_id=%s new_node_count=%s",
        current_request_id(),
        project_id,
        len(roadmap["nodes"]),
    )
    previous_node_count = len(
        session.exec(select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)).all()
    )
    project = replace_project_roadmap_service(session, project_id, roadmap)
    content_preparation = prepare_project_content(
        session, project.id, user_id=user_id, initial_count=0
    )
    logger.info(
        "路线替换完成 request_id=%s project_id=%s previous_node_count=%s new_node_count=%s content_job_id=%s",
        current_request_id(),
        project.id,
        previous_node_count,
        len(roadmap["nodes"]),
        content_preparation.job_id,
    )
    return RoadmapReplacement(
        project_id=project.id,
        previous_node_count=previous_node_count,
        new_node_count=len(roadmap["nodes"]),
        content_preparation=content_preparation,
    )


def audit_project_roadmap(
    session: Session, project_id: int, *, user_id: str = "default"
) -> ProjectRoadmapAudit:
    """只读审计项目路线并返回建议，不保存或替换任何路线数据。"""
    project = _get_project(session, project_id, user_id)
    logger.info(
        "路线审计开始 request_id=%s project_id=%s",
        current_request_id(),
        project_id,
    )
    audit, proposed = audit_existing_roadmap(
        load_roadmap(session, project_id),
        project.topic,
        project.background,
        project.goal,
        project.weekly_hours,
    )
    result = ProjectRoadmapAudit(
        project_id=project_id,
        audit=audit,
        proposed_roadmap=proposed,
    )
    logger.info(
        "路线审计完成 request_id=%s project_id=%s proposed_node_count=%s audit_score=%s",
        current_request_id(),
        project_id,
        len(proposed.get("nodes", [])),
        audit.get("score"),
    )
    return result


def _required_text(value: str, label: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{label}不能为空")
    return normalized


def _weekly_hours(value: float) -> float:
    try:
        hours = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("每周可投入时间必须为正数") from error
    if hours <= 0:
        raise ValueError("每周可投入时间必须为正数")
    return hours

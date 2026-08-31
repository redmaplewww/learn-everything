"""节点本地资料上传与 Kotaemon 索引用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, select

from learning_ext.adapters.kotaemon_rag import (
    IndexDocumentsRequest,
    IndexingEvent,
    KotaemonRagGateway,
)
from learning_ext.application.projects import ApplicationError, NodeNotFoundError, _get_project
from learning_ext.db.models import KnowledgeNode, NodeResource


@dataclass(frozen=True)
class ResourceIndexEvent:
    kind: str
    resource_id: int
    node_id: int
    collection_id: str
    message: str | None = None
    source_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResourceIndexStatus:
    resource_id: int
    node_id: int
    collection_id: str | None
    source_id: str | None
    status: str
    message: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NodeResourceSummary:
    resource_id: int
    node_id: int
    title: str
    rtype: str
    source: str
    status: str
    message: str | None
    collection_id: str | None
    source_id: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResourceDeletionPreview:
    resource: NodeResourceSummary
    confirmation_phrase: str
    index_delete_required: bool

    def to_dict(self) -> dict:
        return {
            "resource": self.resource.to_dict(),
            "confirmation_phrase": self.confirmation_phrase,
            "index_delete_required": self.index_delete_required,
        }


@dataclass(frozen=True)
class ResourceDeletionResult:
    resource_id: int
    node_id: int
    collection_id: str | None
    source_id: str | None
    index_deleted: bool

    def to_dict(self) -> dict:
        return asdict(self)


def stream_index_node_resource(
    session: Session,
    gateway: KotaemonRagGateway,
    *,
    node_id: int,
    path: Path,
    filename: str,
    user_id: str = "default",
) -> Iterator[ResourceIndexEvent]:
    """将已由 HTTP 层安全落盘的单个本地文件索引到其节点资料集合。"""
    node = _get_node(session, node_id, user_id)
    collection_id = _ensure_node_collection(session, gateway, node)
    resource = NodeResource(
        node_id=node_id,
        project_id=node.project_id,
        title=filename,
        url=_resource_url(collection_id, None),
        rtype=_resource_type(path),
        description=_status_description("indexing", None),
        source="user",
    )
    session.add(resource)
    session.commit()
    session.refresh(resource)
    resource_id = _required_resource_id(resource)
    yield ResourceIndexEvent(
        kind="started",
        resource_id=resource_id,
        node_id=node_id,
        collection_id=collection_id,
    )

    final_event: IndexingEvent | None = None
    for event in gateway.index_documents(
        IndexDocumentsRequest(collection_id=collection_id, paths=(path,))
    ):
        if event.kind == "progress":
            yield ResourceIndexEvent(
                kind="progress",
                resource_id=resource_id,
                node_id=node_id,
                collection_id=collection_id,
                message=event.message,
            )
            continue
        final_event = event
        if event.kind == "completed" and event.source_id:
            resource.url = _resource_url(collection_id, event.source_id)
            resource.description = _status_description("completed", event.message)
            session.add(resource)
            session.commit()
            yield ResourceIndexEvent(
                kind="completed",
                resource_id=resource_id,
                node_id=node_id,
                collection_id=collection_id,
                source_id=event.source_id,
                message=event.message,
            )
            return
        if event.kind == "failed":
            resource.description = _status_description("failed", event.message)
            session.add(resource)
            session.commit()
            yield ResourceIndexEvent(
                kind="failed",
                resource_id=resource_id,
                node_id=node_id,
                collection_id=collection_id,
                message=event.message,
            )
            return

    message = (
        final_event.message
        if final_event is not None and final_event.message
        else "底座未返回文件索引结果"
    )
    resource.description = _status_description("failed", message)
    session.add(resource)
    session.commit()
    yield ResourceIndexEvent(
        kind="failed",
        resource_id=resource_id,
        node_id=node_id,
        collection_id=collection_id,
        message=message,
    )


def get_resource_index_status(
    session: Session,
    *,
    node_id: int,
    resource_id: int,
    user_id: str = "default",
) -> ResourceIndexStatus:
    _get_node(session, node_id, user_id)
    resource = session.get(NodeResource, resource_id)
    if resource is None or resource.node_id != node_id:
        raise NodeNotFoundError(f"资料 {resource_id} 不存在")
    collection_id, source_id = _resource_binding(resource.url)
    status, message = _parse_status_description(resource.description)
    return ResourceIndexStatus(
        resource_id=resource_id,
        node_id=node_id,
        collection_id=collection_id,
        source_id=source_id,
        status=status,
        message=message,
    )


def list_node_resources(
    session: Session, *, node_id: int, user_id: str = "default"
) -> list[NodeResourceSummary]:
    _get_node(session, node_id, user_id)
    resources = session.exec(
        select(NodeResource)
        .where(NodeResource.node_id == node_id)
        .order_by(NodeResource.id)
    ).all()
    return [_resource_summary(resource) for resource in resources]


def get_resource_deletion_preview(
    session: Session,
    *,
    node_id: int,
    resource_id: int,
    user_id: str = "default",
) -> ResourceDeletionPreview:
    _get_node(session, node_id, user_id)
    resource = session.get(NodeResource, resource_id)
    if resource is None or resource.node_id != node_id:
        raise NodeNotFoundError(f"资料 {resource_id} 不存在")
    summary = _resource_summary(resource)
    return ResourceDeletionPreview(
        resource=summary,
        confirmation_phrase=f"删除资料 {summary.resource_id}",
        index_delete_required=summary.source_id is not None,
    )


def delete_node_resource(
    session: Session,
    gateway: KotaemonRagGateway,
    *,
    node_id: int,
    resource_id: int,
    confirmation_phrase: str,
    user_id: str = "default",
) -> ResourceDeletionResult:
    preview = get_resource_deletion_preview(
        session, node_id=node_id, resource_id=resource_id, user_id=user_id
    )
    if confirmation_phrase.strip() != preview.confirmation_phrase:
        raise ApplicationError("删除确认短语不匹配")
    resource = session.get(NodeResource, resource_id)
    if resource is None:
        raise NodeNotFoundError(f"资料 {resource_id} 不存在")
    summary = preview.resource
    if summary.source_id:
        if not summary.collection_id:
            raise ApplicationError("资料缺少 RAG 集合绑定，无法删除索引")
        gateway.delete_documents(summary.collection_id, (summary.source_id,))
    session.delete(resource)
    session.commit()
    return ResourceDeletionResult(
        resource_id=resource_id,
        node_id=node_id,
        collection_id=summary.collection_id,
        source_id=summary.source_id,
        index_deleted=summary.source_id is not None,
    )


def _get_node(session: Session, node_id: int, user_id: str) -> KnowledgeNode:
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise NodeNotFoundError(f"知识点 {node_id} 不存在")
    _get_project(session, node.project_id, user_id)
    return node


def _ensure_node_collection(
    session: Session, gateway: KotaemonRagGateway, node: KnowledgeNode
) -> str:
    collection_ids = [item.strip() for item in node.collection_ids.split(",") if item.strip()]
    if collection_ids:
        return collection_ids[0]
    collection = gateway.create_collection(f"learning-node-{node.id}")
    node.collection_ids = collection.id
    session.add(node)
    session.commit()
    return collection.id


def _resource_url(collection_id: str, source_id: str | None) -> str:
    suffix = f"/sources/{source_id}" if source_id else ""
    return f"rag://collections/{collection_id}{suffix}"


def _resource_binding(url: str) -> tuple[str | None, str | None]:
    prefix = "rag://collections/"
    if not url.startswith(prefix):
        return None, None
    rest = url[len(prefix) :]
    collection_id, separator, source_id = rest.partition("/sources/")
    return collection_id or None, source_id if separator and source_id else None


def _status_description(status: str, message: str | None) -> str:
    return f"rag-index-status:{status}\nrag-index-message:{message or ''}"


def _parse_status_description(description: str) -> tuple[str, str | None]:
    lines = description.splitlines()
    status_line = next((line for line in lines if line.startswith("rag-index-status:")), "")
    message_line = next((line for line in lines if line.startswith("rag-index-message:")), "")
    status = status_line.removeprefix("rag-index-status:") or "unknown"
    message = message_line.removeprefix("rag-index-message:") or None
    return status, message


def _resource_type(path: Path) -> str:
    return path.suffix.removeprefix(".").lower() or "doc"


def _resource_summary(resource: NodeResource) -> NodeResourceSummary:
    collection_id, source_id = _resource_binding(resource.url)
    status, message = _parse_status_description(resource.description)
    return NodeResourceSummary(
        resource_id=_required_resource_id(resource),
        node_id=resource.node_id,
        title=resource.title,
        rtype=resource.rtype,
        source=resource.source,
        status=status,
        message=message,
        collection_id=collection_id,
        source_id=source_id,
    )


def _required_resource_id(resource: NodeResource) -> int:
    if resource.id is None:
        raise RuntimeError("资料保存后缺少 ID")
    return resource.id

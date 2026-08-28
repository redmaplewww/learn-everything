from __future__ import annotations

from pathlib import Path

from sqlmodel import select

from learning_ext.adapters.kotaemon_rag import IndexingEvent, RagCollection
from learning_ext.application.resources import (
    get_resource_deletion_preview,
    get_resource_index_status,
    list_node_resources,
    stream_index_node_resource,
)
from learning_ext.db.models import KnowledgeNode, NodeResource


class FakeGateway:
    def __init__(self, events):
        self.events = events
        self.created_names = []

    def create_collection(self, name):
        self.created_names.append(name)
        return RagCollection(id="collection-9", name=name)

    def index_documents(self, _request):
        yield from self.events


def _sample_node(session, project_id):
    return session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).first()


def test_index_resource_persists_collection_binding_and_completed_status(
    session, sample_project, tmp_path
):
    node = _sample_node(session, sample_project.id)
    source = tmp_path / "notes.txt"
    source.write_text("FastAPI 需要调用 application。", encoding="utf-8")
    gateway = FakeGateway(
        [
            IndexingEvent(kind="progress", path=source, message="开始"),
            IndexingEvent(kind="completed", path=source, source_id="source-9"),
        ]
    )

    events = list(
        stream_index_node_resource(
            session,
            gateway,
            node_id=node.id,
            path=source,
            filename="notes.txt",
        )
    )

    assert [event.kind for event in events] == ["started", "progress", "completed"]
    assert node.collection_ids == "collection-9"
    resource = session.get(NodeResource, events[-1].resource_id)
    assert resource.url == "rag://collections/collection-9/sources/source-9"
    status = get_resource_index_status(
        session, node_id=node.id, resource_id=resource.id
    )
    assert status.status == "completed"
    assert status.source_id == "source-9"
    assert gateway.created_names == [f"learning-node-{node.id}"]


def test_index_resource_retains_failure_for_status_read(session, sample_project, tmp_path):
    node = _sample_node(session, sample_project.id)
    source = tmp_path / "broken.txt"
    source.write_text("测试", encoding="utf-8")
    gateway = FakeGateway([IndexingEvent(kind="failed", path=source, message="格式不支持")])

    events = list(
        stream_index_node_resource(
            session,
            gateway,
            node_id=node.id,
            path=source,
            filename="broken.txt",
        )
    )

    assert events[-1].kind == "failed"
    status = get_resource_index_status(
        session, node_id=node.id, resource_id=events[-1].resource_id
    )
    assert (status.status, status.message) == ("failed", "格式不支持")


def test_list_resources_and_preview_deletion_are_read_only(session, sample_project, tmp_path):
    node = _sample_node(session, sample_project.id)
    source = tmp_path / "notes.txt"
    source.write_text("资料", encoding="utf-8")
    gateway = FakeGateway(
        [IndexingEvent(kind="completed", path=source, source_id="source-12")]
    )
    completed = list(
        stream_index_node_resource(
            session,
            gateway,
            node_id=node.id,
            path=source,
            filename="notes.txt",
        )
    )[-1]

    resources = list_node_resources(session, node_id=node.id)
    preview = get_resource_deletion_preview(
        session, node_id=node.id, resource_id=completed.resource_id
    )

    assert [(item.title, item.source_id) for item in resources] == [
        ("notes.txt", "source-12")
    ]
    assert preview.confirmation_phrase == f"删除资料 {completed.resource_id}"
    assert preview.index_delete_required is True

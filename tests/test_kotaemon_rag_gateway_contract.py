from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

from learning_ext.adapters.kotaemon_rag import (
    ChatMessage,
    IndexDocumentsRequest,
    IndexingEvent,
    KotaemonRagGateway,
    RagCollection,
    RagAnswerRequest,
    RagStreamEvent,
    RetrievalRequest,
    RetrievedExcerpt,
    KotaemonRagAdapter,
)


class FakeRagGateway:
    def create_collection(self, name):
        return RagCollection(id="collection-1", name=name)

    def index_documents(self, request):
        yield IndexingEvent(kind="progress", path=request.paths[0], message="开始索引")
        yield IndexingEvent(
            kind="completed", path=request.paths[0], source_id="source-1"
        )

    def retrieve(self, request):
        return [
            RetrievedExcerpt(
                source_id=request.file_ids[0],
                text="学习资料片段",
                score=0.9,
            )
        ]

    def delete_documents(self, _collection_id, _source_ids):
        return None

    def stream_answer(self, request):
        excerpts = tuple(
            self.retrieve(
                RetrievalRequest(
                    collection_id=request.collection_id,
                    query=request.message,
                    file_ids=request.file_ids,
                )
            )
        )
        yield RagStreamEvent(kind="evidence", excerpts=excerpts)
        yield RagStreamEvent(kind="answer_delta", text="分片回答")
        yield RagStreamEvent(kind="citation", excerpts=excerpts)
        yield RagStreamEvent(kind="complete")


def test_fake_gateway_satisfies_rag_contract():
    gateway = FakeRagGateway()
    assert isinstance(gateway, KotaemonRagGateway)

    indexing = list(
        gateway.index_documents(
            IndexDocumentsRequest("collection-1", (Path("sample.txt"),))
        )
    )
    assert [event.kind for event in indexing] == ["progress", "completed"]
    assert indexing[-1].source_id == "source-1"

    answer_events = list(
        gateway.stream_answer(
            RagAnswerRequest(
                collection_id="collection-1",
                conversation_id="conversation-1",
                message="问题",
                history=(ChatMessage(role="user", content="此前问题"),),
                file_ids=("source-1",),
            )
        )
    )
    assert [event.kind for event in answer_events] == [
        "evidence",
        "answer_delta",
        "citation",
        "complete",
    ]
    assert answer_events[0].excerpts[0].text == "学习资料片段"


class FakeDocument:
    def __init__(self, text="资料片段", channel=None):
        self.text = text
        self.content = text
        self.channel = channel
        self.doc_id = "chunk-1"
        self.score = 0.7
        self.metadata = {"file_id": "source-1", "file_name": "sample.txt"}


class FakeRetriever:
    def __call__(self, query):
        return [FakeDocument()]


class FakeReasoning:
    def stream(self, message, conversation_id, history):
        yield FakeDocument("回答分片", channel="chat")
        return type("Answer", (), {"metadata": {"citation": {"source": "source-1"}}})()


def test_adapter_converts_kotaemon_documents_and_stream_events(monkeypatch):
    adapter = KotaemonRagAdapter()
    captured = {}

    def get_retrievers(collection_id, file_ids, limit):
        captured["scope"] = (collection_id, file_ids, limit)
        return [FakeRetriever()]

    monkeypatch.setattr(adapter, "_get_retrievers", get_retrievers)
    monkeypatch.setattr(adapter, "_build_reasoning", lambda retrievers: FakeReasoning())
    request = RagAnswerRequest(
        collection_id="1",
        conversation_id="conversation-1",
        message="问题",
        history=(
            ChatMessage(role="user", content="此前问题"),
            ChatMessage(role="assistant", content="此前回答"),
        ),
        file_ids=("source-1",),
    )

    events = list(adapter.stream_answer(request))

    assert captured["scope"] == ("1", ("source-1",), 5)
    assert [event.kind for event in events] == [
        "evidence",
        "answer_delta",
        "citation",
        "complete",
    ]
    assert events[0].excerpts[0].source_id == "source-1"
    assert events[1].text == "回答分片"


def test_adapter_turns_pipeline_errors_into_error_event(monkeypatch):
    adapter = KotaemonRagAdapter()
    monkeypatch.setattr(
        adapter,
        "_get_retrievers",
        lambda *args: (_ for _ in ()).throw(ValueError("索引不可用")),
    )
    request = RagAnswerRequest("1", "conversation-1", "问题", (), ("source-1",))

    events = list(adapter.stream_answer(request))

    assert [(event.kind, event.text) for event in events] == [("error", "索引不可用")]


def test_adapter_deletes_only_explicit_sources_with_base_index_pipeline(monkeypatch):
    adapter = KotaemonRagAdapter()
    pipeline = object()
    deleted = []

    class FakeIndex:
        def get_indexing_pipeline(self, _settings, _user_id):
            return pipeline

    monkeypatch.setattr(adapter, "_load_index", lambda collection_id: FakeIndex())
    monkeypatch.setattr(
        "ktem.index.file.pipelines.IndexPipeline.delete_file",
        lambda actual_pipeline, source_id: deleted.append((actual_pipeline, source_id)),
    )

    adapter.delete_documents("collection-1", ("source-a", "source-b"))

    assert deleted == [(pipeline, "source-a"), (pipeline, "source-b")]


def test_adapter_uses_active_rag_embedding_for_new_collections(monkeypatch):
    captured = {}

    class FakeEmbeddingManager:
        def get_default_name(self):
            return "learning-rag"

    class FakeIndex:
        id = 12

        def on_start(self):
            captured["started"] = True

    class FakeIndexManager:
        def __init__(self, app):
            captured["app"] = app

        def build_index(self, **kwargs):
            captured.update(kwargs)
            return FakeIndex()

    embeddings_module = ModuleType("ktem.embeddings.manager")
    embeddings_module.embedding_models_manager = FakeEmbeddingManager()
    index_module = ModuleType("ktem.index.manager")
    index_module.IndexManager = FakeIndexManager
    monkeypatch.setitem(sys.modules, "ktem.embeddings.manager", embeddings_module)
    monkeypatch.setitem(sys.modules, "ktem.index.manager", index_module)

    collection = KotaemonRagAdapter(app="application").create_collection("资料库")

    assert collection == RagCollection(id="12", name="资料库")
    assert captured["config"]["embedding"] == "learning-rag"
    assert captured["started"] is True

"""Kotaemon RAG 的客户端无关契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class RagCollection:
    id: str
    name: str


@dataclass(frozen=True)
class IndexDocumentsRequest:
    collection_id: str
    paths: tuple[Path, ...]


@dataclass(frozen=True)
class IndexingEvent:
    kind: Literal["progress", "completed", "failed"]
    path: Path | None = None
    source_id: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class RetrievalRequest:
    collection_id: str
    query: str
    file_ids: tuple[str, ...]
    limit: int = 5


@dataclass(frozen=True)
class RetrievedExcerpt:
    source_id: str
    text: str
    score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class RagAnswerRequest:
    collection_id: str
    conversation_id: str
    message: str
    history: tuple[ChatMessage, ...]
    file_ids: tuple[str, ...]


@dataclass(frozen=True)
class RagStreamEvent:
    kind: Literal["evidence", "answer_delta", "citation", "complete", "error"]
    text: str | None = None
    excerpts: tuple[RetrievedExcerpt, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class KotaemonRagGateway(Protocol):
    """application 使用的 RAG 能力边界。"""

    def create_collection(self, name: str) -> RagCollection:
        """创建资料集合，并返回可持久化的集合标识。"""

    def index_documents(self, request: IndexDocumentsRequest) -> Iterator[IndexingEvent]:
        """索引文档，并报告可观察的逐文件进度。"""

    def retrieve(self, request: RetrievalRequest) -> list[RetrievedExcerpt]:
        """在显式文件范围内返回检索片段。"""

    def delete_documents(self, collection_id: str, source_ids: tuple[str, ...]) -> None:
        """仅删除给定集合中的显式资料 source。"""

    def stream_answer(self, request: RagAnswerRequest) -> Iterator[RagStreamEvent]:
        """产生结构化 RAG 回答事件，并以 complete 或 error 结束。"""


class _ExplicitSelectionAdapter:
    def get_selected_ids(self, selected: Sequence[str] | None) -> list[str]:
        if selected is None:
            return []
        if not all(isinstance(item, str) for item in selected):
            raise ValueError("文件范围必须是文件 ID 或 JSON 编码的文件组 ID")
        return list(selected)


class KotaemonRagAdapter:
    """将 Kotaemon 底层索引和 reasoning pipeline 映射到项目契约。"""

    def __init__(
        self,
        *,
        app: object | None = None,
        user_id: str | None = None,
        reasoning_settings: Mapping[str, Any] | None = None,
    ) -> None:
        self._app = app or object()
        self._user_id = user_id
        self._reasoning_settings = dict(reasoning_settings or {})

    def create_collection(self, name: str) -> RagCollection:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("资料集合名称不能为空")

        from ktem.embeddings.manager import embedding_models_manager
        from ktem.index.manager import IndexManager

        index = IndexManager(app=self._app).build_index(
            name=normalized_name,
            config={
                "embedding": embedding_models_manager.get_default_name(),
                "supported_file_types": ".txt,.md,.pdf,.docx,.html",
                "private": False,
            },
            index_type="ktem.index.file.index.FileIndex",
        )
        index.on_start()
        return RagCollection(id=str(index.id), name=normalized_name)

    def index_documents(self, request: IndexDocumentsRequest) -> Iterator[IndexingEvent]:
        try:
            index = self._load_index(request.collection_id)
            pipeline = index.get_indexing_pipeline({}, self._user_id)
            stream = pipeline.stream(list(request.paths))
            try:
                while True:
                    document = next(stream)
                    content = document.content
                    if document.channel == "index" and isinstance(content, dict):
                        path = content.get("file_path")
                        yield IndexingEvent(
                            kind="completed" if content.get("status") == "success" else "failed",
                            path=Path(path) if path else None,
                            message=content.get("message"),
                        )
                    elif document.channel == "debug":
                        yield IndexingEvent(kind="progress", message=str(content))
            except StopIteration as completed:
                file_ids, errors, _ = completed.value
                for path, file_id, error in zip(request.paths, file_ids, errors):
                    if error is None:
                        yield IndexingEvent(kind="completed", path=path, source_id=file_id)
                    else:
                        yield IndexingEvent(kind="failed", path=path, message=error)
        except Exception as error:
            yield IndexingEvent(kind="failed", message=str(error))

    def retrieve(self, request: RetrievalRequest) -> list[RetrievedExcerpt]:
        retrievers = self._get_retrievers(
            request.collection_id, request.file_ids, request.limit
        )
        documents = []
        for retriever in retrievers:
            documents.extend(retriever(request.query))
        return self._to_excerpts(documents)

    def delete_documents(self, collection_id: str, source_ids: tuple[str, ...]) -> None:
        if not source_ids:
            return
        from ktem.index.file.pipelines import IndexPipeline

        index = self._load_index(collection_id)
        pipeline = index.get_indexing_pipeline({}, self._user_id)
        for source_id in source_ids:
            IndexPipeline.delete_file(pipeline, source_id)

    def stream_answer(self, request: RagAnswerRequest) -> Iterator[RagStreamEvent]:
        try:
            retrievers = self._get_retrievers(
                request.collection_id, request.file_ids, 5
            )
            evidence = self._retrieve_with(retrievers, request.message)
            if evidence:
                yield RagStreamEvent(kind="evidence", excerpts=tuple(evidence))

            pipeline = self._build_reasoning(retrievers)
            history = self._to_reasoning_history(request.history)
            stream = pipeline.stream(request.message, request.conversation_id, history)
            try:
                while True:
                    document = next(stream)
                    if document.channel == "chat" and document.content:
                        yield RagStreamEvent(kind="answer_delta", text=str(document.content))
            except StopIteration as completed:
                answer = completed.value
                citation = answer.metadata.get("citation") if answer else None
                if citation:
                    yield RagStreamEvent(
                        kind="citation",
                        metadata={"citation": citation},
                    )
                yield RagStreamEvent(kind="complete")
        except Exception as error:
            yield RagStreamEvent(kind="error", text=str(error))

    def _load_index(self, collection_id: str):
        try:
            index_id = int(collection_id)
        except ValueError as error:
            raise ValueError(f"无效的 RAG collection_id: {collection_id}") from error
        if index_id <= 0:
            raise ValueError(f"无效的 RAG collection_id: {collection_id}")

        from sqlmodel import Session

        from ktem.db.engine import engine
        from ktem.index.manager import IndexManager
        from ktem.index.models import Index

        with Session(engine) as session:
            entry = session.get(Index, index_id)
            if entry is None:
                raise ValueError(f"RAG collection {collection_id} 不存在")
            name, config, index_type = entry.name, dict(entry.config), entry.index_type
        return IndexManager(app=self._app).start_index(index_id, name, config, index_type)

    def _get_retrievers(
        self, collection_id: str, file_ids: Sequence[str], limit: int
    ) -> list[Any]:
        if limit <= 0:
            raise ValueError("检索数量必须大于 0")
        index = self._load_index(collection_id)
        index._selector_ui = _ExplicitSelectionAdapter()
        prefix = f"index.options.{index.id}."
        settings = {
            f"{prefix}prioritize_table": False,
            f"{prefix}num_retrieval": limit,
            f"{prefix}mmr": False,
            f"{prefix}retrieval_mode": "hybrid",
            f"{prefix}use_llm_reranking": False,
            f"{prefix}use_reranking": False,
            f"{prefix}reranking_llm": None,
        }
        return index.get_retriever_pipelines(settings, self._user_id, list(file_ids))

    def _build_reasoning(self, retrievers: list[Any]):
        from ktem.reasoning.simple import FullQAPipeline

        settings = self._default_reasoning_settings()
        settings.update(self._reasoning_settings)
        return FullQAPipeline.get_pipeline(settings, {"app": {"regen": False}}, retrievers)

    def _default_reasoning_settings(self) -> dict[str, Any]:
        from ktem.reasoning.simple import FullQAPipeline

        prefix = "reasoning.options.simple"
        defaults = FullQAPipeline.get_user_settings()
        return {
            "reasoning.max_context_length": 32000,
            "reasoning.lang": "English",
            f"{prefix}.llm": defaults["llm"]["value"],
            f"{prefix}.highlight_citation": "off",
            f"{prefix}.create_mindmap": False,
            f"{prefix}.create_citation_viz": False,
            f"{prefix}.use_multimodal": False,
            f"{prefix}.system_prompt": defaults["system_prompt"]["value"],
            f"{prefix}.qa_prompt": defaults["qa_prompt"]["value"],
            f"{prefix}.n_last_interactions": defaults["n_last_interactions"]["value"],
            f"{prefix}.trigger_context": defaults["trigger_context"]["value"],
        }

    def _retrieve_with(self, retrievers: list[Any], query: str) -> list[RetrievedExcerpt]:
        documents = []
        for retriever in retrievers:
            documents.extend(retriever(query))
        return self._to_excerpts(documents)

    @staticmethod
    def _to_reasoning_history(history: Sequence[ChatMessage]) -> list[tuple[str, str]]:
        pairs = []
        pending_user = None
        for item in history:
            if item.role == "user":
                pending_user = item.content
            elif pending_user is not None:
                pairs.append((pending_user, item.content))
                pending_user = None
        return pairs

    @staticmethod
    def _to_excerpts(documents: Sequence[Any]) -> list[RetrievedExcerpt]:
        excerpts = []
        seen_ids = set()
        for document in documents:
            document_id = str(document.doc_id)
            if document_id in seen_ids:
                continue
            seen_ids.add(document_id)
            excerpts.append(
                RetrievedExcerpt(
                    source_id=str(document.metadata.get("file_id", document_id)),
                    text=document.text,
                    score=getattr(document, "score", None),
                    metadata=dict(document.metadata),
                )
            )
        return excerpts

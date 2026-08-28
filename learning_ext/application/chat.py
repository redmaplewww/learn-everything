"""RAG 对话的客户端无关 application 用例。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

from learning_ext.adapters.kotaemon_rag import (
    ChatMessage,
    KotaemonRagGateway,
    RagAnswerRequest,
    RagStreamEvent,
)


@dataclass(frozen=True)
class RagChatRequest:
    collection_id: str
    conversation_id: str
    message: str
    history: tuple[ChatMessage, ...]
    file_ids: tuple[str, ...]


def stream_rag_chat(
    gateway: KotaemonRagGateway, request: RagChatRequest
) -> Iterator[RagStreamEvent]:
    """执行一次有明确范围和终止事件的 RAG 对话。"""
    message = request.message.strip()
    if not message:
        yield RagStreamEvent(kind="error", text="问题不能为空")
        return
    if not request.collection_id:
        yield RagStreamEvent(kind="error", text="必须选择资料集合")
        return
    if not request.file_ids:
        yield RagStreamEvent(kind="error", text="必须选择至少一份资料")
        return

    try:
        events = gateway.stream_answer(
            RagAnswerRequest(
                collection_id=request.collection_id,
                conversation_id=request.conversation_id,
                message=message,
                history=request.history,
                file_ids=request.file_ids,
            )
        )
        for event in events:
            yield event
            if event.kind in {"complete", "error"}:
                return
        yield RagStreamEvent(kind="complete")
    except Exception as error:
        yield RagStreamEvent(kind="error", text=str(error))

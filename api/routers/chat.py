"""RAG SSE 对话接口。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.dependencies import get_rag_gateway
from api.schemas.chat import RagChatStreamRequest
from learning_ext.adapters.kotaemon_rag import ChatMessage, KotaemonRagGateway
from learning_ext.application.chat import RagChatRequest, stream_rag_chat

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/stream")
async def stream_chat(
    payload: RagChatStreamRequest,
    request: Request,
    gateway: KotaemonRagGateway = Depends(get_rag_gateway),
):
    chat_request = RagChatRequest(
        collection_id=payload.collection_id,
        conversation_id=payload.conversation_id,
        message=payload.message,
        history=tuple(ChatMessage(role=item.role, content=item.content) for item in payload.history),
        file_ids=tuple(payload.file_ids),
    )

    async def events():
        for event in stream_rag_chat(gateway, chat_request):
            if await request.is_disconnected():
                return
            body = {
                "text": event.text,
                "excerpts": [excerpt.__dict__ for excerpt in event.excerpts],
                "metadata": dict(event.metadata),
            }
            yield f"event: {event.kind}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")

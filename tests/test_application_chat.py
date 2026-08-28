from __future__ import annotations

from learning_ext.adapters.kotaemon_rag import RagStreamEvent
from learning_ext.application.chat import RagChatRequest, stream_rag_chat


class FakeGateway:
    def stream_answer(self, request):
        yield RagStreamEvent(kind="answer_delta", text=request.message)
        yield RagStreamEvent(kind="complete")


def test_stream_rag_chat_delegates_only_to_gateway():
    events = list(
        stream_rag_chat(
            FakeGateway(),
            RagChatRequest("collection-1", "conv-1", "  问题  ", (), ("file-1",)),
        )
    )

    assert [(event.kind, event.text) for event in events] == [
        ("answer_delta", "问题"),
        ("complete", None),
    ]


def test_stream_rag_chat_rejects_missing_scope():
    events = list(
        stream_rag_chat(
            FakeGateway(),
            RagChatRequest("collection-1", "conv-1", "问题", (), ()),
        )
    )

    assert [(event.kind, event.text) for event in events] == [
        ("error", "必须选择至少一份资料")
    ]

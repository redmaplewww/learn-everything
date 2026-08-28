from __future__ import annotations

import pytest

from kotaemon.base import Document, RetrievedDocument
from ktem.reasoning.base import BaseReasoning


class FakeRetriever:
    def __call__(self, message: str):
        return [RetrievedDocument(text=f"证据：{message}", score=1.0)]


class FailingRetriever:
    def __call__(self, message: str):
        raise RuntimeError("检索器不可用")


class ContractReasoning(BaseReasoning):
    retrievers: list

    @classmethod
    def get_pipeline(cls, user_settings, state, retrievers=None):
        return cls(retrievers=retrievers or [])

    def stream(self, message, conv_id, history, **kwargs):
        docs = self.retrievers[0](message)
        yield Document(channel="info", content=docs[0].text)
        yield Document(channel="chat", content="分片回答")
        return Document(text="最终回答", metadata={"citation": [docs[0].doc_id]})


def test_reasoning_stream_contract_is_client_independent():
    pipeline = ContractReasoning.get_pipeline({}, {}, [FakeRetriever()])
    stream = pipeline.stream("检索问题", "conv-1", [])
    events = []
    try:
        while True:
            events.append(next(stream))
    except StopIteration as completed:
        answer = completed.value

    assert [(event.channel, event.content) for event in events] == [
        ("info", "证据：检索问题"),
        ("chat", "分片回答"),
    ]
    assert answer.text == "最终回答"
    assert answer.metadata["citation"]


def test_reasoning_stream_propagates_retriever_errors():
    pipeline = ContractReasoning.get_pipeline({}, {}, [FailingRetriever()])

    with pytest.raises(RuntimeError, match="检索器不可用"):
        next(pipeline.stream("检索问题", "conv-1", []))

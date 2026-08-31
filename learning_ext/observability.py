"""学习服务的请求可观测上下文。"""

from __future__ import annotations

from contextvars import ContextVar


_request_id: ContextVar[str] = ContextVar("learning_request_id", default="-")


def set_request_id(value: str):
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def current_request_id() -> str:
    return _request_id.get()

"""LLM 调用封装 (直连版)。

直接读取 kotaemon/.env 的 OpenAI 兼容配置，用 openai SDK 调用，
完全绕过 Kotaemon 的 llms manager，避免运行时更新和 PromptType 等 import 问题。

配置来源 (按优先级)：
    1. kotaemon/.env 文件 (由「⚡ 模型配置」页写入)
    2. 进程环境变量 (Kotaemon 启动时 decouple 已加载)
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Iterator, Optional

# .env 路径
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / "kotaemon" / ".env"

# 配置缓存 (5 秒内复用，配置页保存后最多 5 秒生效)
_cache: dict = {"ts": 0.0, "data": {}}
_CACHE_TTL = 5.0


def invalidate_cache() -> None:
    """强制清空配置缓存, 让 .env 改动立即生效。配置页保存后调用。"""
    _cache["data"] = {}
    _cache["ts"] = 0.0


def _parse_env_file() -> dict:
    """解析 .env 文件为 dict"""
    data: dict[str, str] = {}
    if not _ENV_FILE.exists():
        return data
    try:
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip("\"'")
    except Exception:
        pass
    return data


def _load_config() -> dict:
    """加载 LLM 配置 (.env 文件 + 环境变量，带缓存)"""
    now = time.time()
    if now - _cache["ts"] < _CACHE_TTL and _cache["data"]:
        return _cache["data"]

    file_cfg = _parse_env_file()
    cfg = {
        "api_key": (
            file_cfg.get("LEARNING_LLM_API_KEY")
            or file_cfg.get("OPENAI_API_KEY")
            or os.environ.get("LEARNING_LLM_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        ),
        "base_url": (
            file_cfg.get("LEARNING_LLM_API_BASE")
            or file_cfg.get("OPENAI_API_BASE")
            or os.environ.get("LEARNING_LLM_API_BASE", "")
            or os.environ.get("OPENAI_API_BASE", "")
            or "https://api.openai.com/v1"
        ),
        "chat_model": (
            file_cfg.get("LEARNING_LLM_MODEL")
            or file_cfg.get("OPENAI_CHAT_MODEL")
            or os.environ.get("LEARNING_LLM_MODEL", "")
            or os.environ.get("OPENAI_CHAT_MODEL", "")
            or "gpt-4o-mini"
        ),
        "embed_model": (
            file_cfg.get("OPENAI_EMBEDDINGS_MODEL")
            or os.environ.get("OPENAI_EMBEDDINGS_MODEL", "")
        ),
    }
    # 过滤占位符
    if "请在UI" in cfg["api_key"] or "YOUR" in cfg["api_key"]:
        cfg["api_key"] = ""
    _cache["data"] = cfg
    _cache["ts"] = now
    return cfg


def _get_client():
    """构造 openai 客户端"""
    from openai import OpenAI

    cfg = _load_config()
    if not cfg["api_key"]:
        raise RuntimeError(
            "未配置 API Key。请到「⚡ 模型配置」Tab 填入 API Key 并保存。"
        )
    # timeout: 连接 10s, 读取 120s (LLM 生成可能慢)
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=120.0), cfg


def chat(
    prompt: str,
    *,
    system: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    stream: bool = False,
    max_tokens: Optional[int] = None,
    retries: int = 2,
) -> str | Iterator[str]:
    """单轮对话 (带超时 + 自动重试)。

    Args:
        prompt: 用户消息
        system: 可选系统提示
        model_name: 模型名 (None 用 .env 默认)
        temperature: 温度
        stream: 流式返回
        max_tokens: 最大输出 token
        retries: 失败重试次数 (网络瞬断/限流时)
    """
    import logging
    import time

    log = logging.getLogger("learning_ext.llm")

    client, cfg = _get_client()
    model = model_name or cfg["chat_model"]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    if stream:
        resp = client.chat.completions.create(stream=True, **kwargs)
        return _stream_iter(resp)

    # 非流式: 带重试
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            if not content.strip():
                raise RuntimeError(
                    f"模型 `{model}` 返回了空回复。可能是模型名错误或内容被过滤。"
                    f"请到「⚡ 模型配置」检查模型名 (DeepSeek 应为 deepseek-chat)。"
                )
            return content
        except RuntimeError:
            raise  # 空回复不重试, 直接抛
        except Exception as e:
            last_err = e
            err_type = type(e).__name__
            # 限流/超时/连接错误 才重试; 鉴权错误不重试
            retryable = any(
                kw in err_type.lower() or kw in str(e).lower()
                for kw in (
                    "timeout",
                    "connection",
                    "ratelimit",
                    "temp",
                    "unavailable",
                    "overloaded",
                )
            )
            if not retryable or attempt == retries:
                raise
            wait = 2**attempt  # 1s, 2s, 4s
            log.warning(
                f"LLM 调用失败 ({err_type}), {wait}s 后重试 ({attempt + 1}/{retries}): {e}"
            )
            time.sleep(wait)
    raise RuntimeError(f"LLM 调用重试 {retries} 次仍失败: {last_err}")


def _stream_iter(resp) -> Iterator[str]:
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_json(
    prompt: str,
    *,
    system: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict | list:
    """要求 LLM 返回 JSON 并解析 (容错提取)。

    自动剥离 markdown ```json 代码块标记。
    Returns:
        解析后的 dict 或 list
    """
    raw = chat(prompt, system=system, model_name=model_name, temperature=0.1)
    # 剥 markdown 代码块
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    # 尝试直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 容错：提取首个 JSON 块 (支持 {} 和 [])
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    raise ValueError(
        f"LLM 未返回有效 JSON。模型: {_load_config()['chat_model']}\n"
        f"原始回复前 500 字: {raw[:500]}"
    )


def get_llm(model_name: Optional[str] = None):
    """兼容接口：返回一个简单的可调用对象 (带 .invoke/.stream)。

    供少量仍按 Kotaemon 风格调用的代码使用。
    """

    class _LLMWrapper:
        def __init__(self, model: str):
            self.model = model

        def invoke(self, prompt: str, *, system: Optional[str] = None) -> str:
            return chat(prompt, system=system, model_name=self.model)

        def stream(self, prompt: str, *, system: Optional[str] = None):
            return chat(prompt, system=system, model_name=self.model, stream=True)

        def __call__(self, prompt: str, *, system: Optional[str] = None) -> str:
            return chat(prompt, system=system, model_name=self.model)

    return _LLMWrapper(model_name or _load_config()["chat_model"])

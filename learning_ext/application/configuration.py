"""本地单用户模型配置用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from learning_ext.application.projects import ApplicationError


class ModelConfigurationError(ApplicationError):
    """模型配置不满足日常学习运行要求。"""


@dataclass(frozen=True)
class ModelConfigurationInput:
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str = ""


@dataclass(frozen=True)
class ModelConfigurationStatus:
    base_url: str
    chat_model: str
    embedding_model: str
    api_key_configured: bool
    chat_ready: bool
    rag_ready: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelConnectivity:
    ok: bool
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class ModelConfigurationService:
    """隔离 .env 格式和 Kotaemon 运行时模型池更新。"""

    def __init__(
        self,
        *,
        env_path: Path | None = None,
        runtime_apply: Callable[[ModelConfigurationInput], None] | None = None,
        requester: Callable[..., object] | None = None,
    ) -> None:
        self._env_path = env_path or Path(__file__).resolve().parents[2] / "kotaemon" / ".env"
        self._runtime_apply = runtime_apply or _apply_runtime_models
        self._requester = requester or _post_chat_completion

    def get_status(self) -> ModelConfigurationStatus:
        raw = _read_env(self._env_path)
        api_key = _clean_api_key(raw.get("OPENAI_API_KEY", ""))
        base_url = raw.get("OPENAI_API_BASE", "") or "https://api.openai.com/v1"
        chat_model = raw.get("OPENAI_CHAT_MODEL", "") or "gpt-4o-mini"
        embedding_model = raw.get("OPENAI_EMBEDDINGS_MODEL", "")
        return ModelConfigurationStatus(
            base_url=base_url,
            chat_model=chat_model,
            embedding_model=embedding_model,
            api_key_configured=bool(api_key),
            chat_ready=bool(api_key and chat_model),
            rag_ready=bool(api_key and embedding_model),
        )

    def save(self, config: ModelConfigurationInput) -> ModelConfigurationStatus:
        normalized = _normalize(config)
        _write_env(
            self._env_path,
            {
                "OPENAI_API_BASE": normalized.base_url,
                "OPENAI_API_KEY": normalized.api_key,
                "OPENAI_CHAT_MODEL": normalized.chat_model,
                "OPENAI_EMBEDDINGS_MODEL": normalized.embedding_model,
            },
        )
        from learning_ext.llm.client import invalidate_cache

        invalidate_cache()
        self._runtime_apply(normalized)
        return self.get_status()

    def test(self, config: ModelConfigurationInput) -> ModelConnectivity:
        normalized = _normalize(config)
        response = self._requester(
            f"{normalized.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {normalized.api_key}"},
            json={
                "model": normalized.chat_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0,
            },
            timeout=15,
        )
        status_code = int(getattr(response, "status_code", 0))
        if 200 <= status_code < 300:
            return ModelConnectivity(ok=True, message="对话模型连接成功")
        raise ModelConfigurationError(f"对话模型连接失败（HTTP {status_code or '未知'}）")


def _normalize(config: ModelConfigurationInput) -> ModelConfigurationInput:
    base_url = config.base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ModelConfigurationError("base_url 必须是有效的 HTTP/HTTPS 地址")
    if parsed.username or parsed.password:
        raise ModelConfigurationError("base_url 不能包含认证信息")
    api_key = _clean_api_key(config.api_key)
    chat_model = config.chat_model.strip()
    embedding_model = config.embedding_model.strip()
    if not api_key:
        raise ModelConfigurationError("api_key 不能为空")
    if not chat_model:
        raise ModelConfigurationError("chat_model 不能为空")
    if len(base_url) > 500 or len(api_key) > 2000 or len(chat_model) > 200:
        raise ModelConfigurationError("模型配置字段长度超出允许范围")
    if len(embedding_model) > 200:
        raise ModelConfigurationError("embedding_model 长度超出允许范围")
    if any("\n" in value or "\r" in value for value in (base_url, api_key, chat_model, embedding_model)):
        raise ModelConfigurationError("模型配置字段不能包含换行符")
    return ModelConfigurationInput(base_url, api_key, chat_model, embedding_model)


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _write_env(path: Path, updates: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output = []
    for line in existing:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _clean_api_key(value: str) -> str:
    cleaned = value.strip()
    return "" if "请在UI" in cleaned or "YOUR" in cleaned else cleaned


def _post_chat_completion(url: str, **kwargs):
    import requests

    return requests.post(url, **kwargs)


def _apply_runtime_models(config: ModelConfigurationInput) -> None:
    from ktem.embeddings.manager import embedding_models_manager
    from ktem.llms.manager import llms

    chat_spec = {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "temperature": 0.3,
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.chat_model,
        "timeout": 60,
    }
    _upsert_model(llms, "learning-openai", chat_spec)
    if config.embedding_model:
        embedding_spec = {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": config.base_url,
            "api_key": config.api_key,
            "model": config.embedding_model,
            "timeout": 30,
        }
        _upsert_model(embedding_models_manager, "learning-openai", embedding_spec)


def _upsert_model(manager, name: str, spec: dict) -> None:
    if name in manager.info():
        manager.update(name, spec=spec, default=True)
    else:
        manager.add(name, spec=spec, default=True)

"""本地单用户的 LLM 与 RAG 向量模型配置用例。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse
from uuid import uuid4

from learning_ext.application.projects import ApplicationError

ConfigurationKind = Literal["llm", "rag"]


class ModelConfigurationError(ApplicationError):
    """模型配置不满足日常学习运行要求。"""


@dataclass(frozen=True)
class ModelEndpointInput:
    name: str
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class ModelProfileSummary:
    id: str
    name: str
    base_url: str
    model: str
    api_key_configured: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelEndpointStatus:
    active_profile_id: str | None
    active_profile_name: str | None
    base_url: str
    model: str
    api_key_configured: bool
    ready: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelConfigurationStatus:
    llm: ModelEndpointStatus
    rag: ModelEndpointStatus
    llm_profiles: tuple[ModelProfileSummary, ...]
    rag_profiles: tuple[ModelProfileSummary, ...]

    def to_dict(self) -> dict:
        return {
            "llm": self.llm.to_dict(),
            "rag": self.rag.to_dict(),
            "llm_profiles": [profile.to_dict() for profile in self.llm_profiles],
            "rag_profiles": [profile.to_dict() for profile in self.rag_profiles],
        }


@dataclass(frozen=True)
class ModelConnectivity:
    ok: bool
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class ModelConfigurationService:
    """隔离档案存储、.env 兼容层和 Kotaemon 运行时模型池更新。"""

    def __init__(
        self,
        *,
        env_path: Path | None = None,
        profiles_path: Path | None = None,
        runtime_apply: Callable[[ConfigurationKind, ModelEndpointInput], None]
        | None = None,
        requester: Callable[..., object] | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        self._env_path = env_path or root / "kotaemon" / ".env"
        self._profiles_path = (
            profiles_path
            or root / "kotaemon" / "ktem_app_data" / "user_data" / "model_profiles.json"
        )
        self._runtime_apply = runtime_apply or _apply_runtime_model
        self._requester = requester or _post_request

    def get_status(self) -> ModelConfigurationStatus:
        return self._to_status(self._load_profiles())

    def create_profile(
        self, kind: ConfigurationKind, name: str
    ) -> ModelConfigurationStatus:
        profiles = self._load_profiles()
        profile = {
            "id": uuid4().hex,
            "name": _normalize_name(name),
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini" if kind == "llm" else "text-embedding-3-small",
        }
        profiles[f"{kind}_profiles"].append(profile)
        profiles[f"active_{kind}_profile_id"] = profile["id"]
        self._write_profiles(profiles)
        return self._to_status(profiles)

    def save(
        self, kind: ConfigurationKind, profile_id: str, config: ModelEndpointInput
    ) -> ModelConfigurationStatus:
        profiles = self._load_profiles()
        profile = self._find_profile(profiles, kind, profile_id)
        normalized = _normalize(config, existing_api_key=str(profile["api_key"]))
        profile.update(asdict(normalized))
        profiles[f"active_{kind}_profile_id"] = profile_id
        self._apply_active(kind, normalized)
        self._write_profiles(profiles)
        return self._to_status(profiles)

    def activate(
        self, kind: ConfigurationKind, profile_id: str
    ) -> ModelConfigurationStatus:
        profiles = self._load_profiles()
        profile = self._find_profile(profiles, kind, profile_id)
        profiles[f"active_{kind}_profile_id"] = profile_id
        endpoint = _profile_input(profile)
        if _is_ready(endpoint):
            self._apply_active(kind, endpoint)
        self._write_profiles(profiles)
        return self._to_status(profiles)

    def delete_profile(
        self, kind: ConfigurationKind, profile_id: str
    ) -> ModelConfigurationStatus:
        profiles = self._load_profiles()
        self._find_profile(profiles, kind, profile_id)
        key = f"{kind}_profiles"
        remaining = [
            profile for profile in profiles[key] if profile["id"] != profile_id
        ]
        active_key = f"active_{kind}_profile_id"
        if profiles[active_key] == profile_id:
            if not remaining:
                raise ModelConfigurationError("每类模型至少保留一个档案")
            fallback = _profile_input(remaining[0])
            if not _is_ready(fallback):
                raise ModelConfigurationError(
                    "请先配置可用的其他档案，再删除当前活动档案"
                )
            profiles[active_key] = remaining[0]["id"]
            self._apply_active(kind, fallback)
        profiles[key] = remaining
        self._write_profiles(profiles)
        return self._to_status(profiles)

    def test(
        self,
        kind: ConfigurationKind,
        config: ModelEndpointInput,
        profile_id: str | None = None,
    ) -> ModelConnectivity:
        existing_api_key = ""
        if profile_id:
            existing_api_key = str(
                self._find_profile(self._load_profiles(), kind, profile_id)["api_key"]
            )
        normalized = _normalize(config, existing_api_key=existing_api_key)
        endpoint = "/chat/completions" if kind == "llm" else "/embeddings"
        payload = (
            {
                "model": normalized.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0,
            }
            if kind == "llm"
            else {"model": normalized.model, "input": "ping"}
        )
        response = self._requester(
            f"{normalized.base_url.rstrip('/')}{endpoint}",
            headers={"Authorization": f"Bearer {normalized.api_key}"},
            json=payload,
            timeout=15,
        )
        status_code = int(getattr(response, "status_code", 0))
        if 200 <= status_code < 300:
            return ModelConnectivity(
                ok=True,
                message="对话模型连接成功" if kind == "llm" else "RAG 向量模型连接成功",
            )
        label = "对话模型" if kind == "llm" else "RAG 向量模型"
        raise ModelConfigurationError(
            f"{label}连接失败（HTTP {status_code or '未知'}）"
        )

    def apply_active_profiles(self) -> None:
        profiles = self._load_profiles()
        for kind in ("llm", "rag"):
            profile_id = profiles[f"active_{kind}_profile_id"]
            if not profile_id:
                continue
            endpoint = _profile_input(self._find_profile(profiles, kind, profile_id))
            if _is_ready(endpoint):
                self._runtime_apply(kind, endpoint)

    def _apply_active(
        self, kind: ConfigurationKind, config: ModelEndpointInput
    ) -> None:
        original = _write_env(self._env_path, _env_updates(kind, config))
        try:
            if kind == "llm":
                from learning_ext.llm.client import invalidate_cache

                invalidate_cache()
            self._runtime_apply(kind, config)
        except Exception:
            _restore_env(self._env_path, original)
            raise

    def _load_profiles(self) -> dict:
        if self._profiles_path.exists():
            try:
                loaded = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ModelConfigurationError("模型档案文件无法读取") from error
            return _validate_profiles(loaded)
        return _legacy_profiles(_read_env(self._env_path))

    def _write_profiles(self, profiles: dict) -> None:
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(
            json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _find_profile(
        self, profiles: dict, kind: ConfigurationKind, profile_id: str
    ) -> dict:
        for profile in profiles[f"{kind}_profiles"]:
            if profile["id"] == profile_id:
                return profile
        raise ModelConfigurationError("模型档案不存在")

    def _to_status(self, profiles: dict) -> ModelConfigurationStatus:
        return ModelConfigurationStatus(
            llm=_endpoint_status(profiles, "llm"),
            rag=_endpoint_status(profiles, "rag"),
            llm_profiles=tuple(
                _profile_summary(profile) for profile in profiles["llm_profiles"]
            ),
            rag_profiles=tuple(
                _profile_summary(profile) for profile in profiles["rag_profiles"]
            ),
        )


def _legacy_profiles(raw: dict[str, str]) -> dict:
    llm = {
        "id": "legacy-llm",
        "name": "默认 LLM",
        "base_url": raw.get("LEARNING_LLM_API_BASE")
        or raw.get("OPENAI_API_BASE")
        or "https://api.openai.com/v1",
        "api_key": _clean_api_key(
            raw.get("LEARNING_LLM_API_KEY") or raw.get("OPENAI_API_KEY", "")
        ),
        "model": raw.get("LEARNING_LLM_MODEL")
        or raw.get("OPENAI_CHAT_MODEL")
        or "gpt-4o-mini",
    }
    rag = {
        "id": "legacy-rag",
        "name": "默认 RAG",
        "base_url": raw.get("LEARNING_RAG_API_BASE")
        or raw.get("OPENAI_API_BASE")
        or "https://api.openai.com/v1",
        "api_key": _clean_api_key(
            raw.get("LEARNING_RAG_API_KEY") or raw.get("OPENAI_API_KEY", "")
        ),
        "model": raw.get("LEARNING_RAG_EMBEDDING_MODEL")
        or raw.get("OPENAI_EMBEDDINGS_MODEL", ""),
    }
    return {
        "version": 1,
        "active_llm_profile_id": llm["id"],
        "active_rag_profile_id": rag["id"],
        "llm_profiles": [llm],
        "rag_profiles": [rag],
    }


def _validate_profiles(value: object) -> dict:
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ModelConfigurationError("模型档案文件格式不兼容")
    for kind in ("llm", "rag"):
        profiles = value.get(f"{kind}_profiles")
        active = value.get(f"active_{kind}_profile_id")
        if not isinstance(profiles, list) or (
            active is not None and not isinstance(active, str)
        ):
            raise ModelConfigurationError("模型档案文件格式不兼容")
        for profile in profiles:
            if not isinstance(profile, dict) or not all(
                isinstance(profile.get(key), str)
                for key in ("id", "name", "base_url", "api_key", "model")
            ):
                raise ModelConfigurationError("模型档案文件格式不兼容")
    return value


def _endpoint_status(profiles: dict, kind: ConfigurationKind) -> ModelEndpointStatus:
    profile_id = profiles[f"active_{kind}_profile_id"]
    profile = next(
        (item for item in profiles[f"{kind}_profiles"] if item["id"] == profile_id),
        None,
    )
    if profile is None:
        return ModelEndpointStatus(None, None, "", "", False, False)
    endpoint = _profile_input(profile)
    return ModelEndpointStatus(
        profile_id,
        endpoint.name,
        endpoint.base_url,
        endpoint.model,
        bool(endpoint.api_key),
        _is_ready(endpoint),
    )


def _profile_summary(profile: dict) -> ModelProfileSummary:
    endpoint = _profile_input(profile)
    return ModelProfileSummary(
        str(profile["id"]),
        endpoint.name,
        endpoint.base_url,
        endpoint.model,
        bool(endpoint.api_key),
    )


def _profile_input(profile: dict) -> ModelEndpointInput:
    return ModelEndpointInput(
        str(profile["name"]),
        str(profile["base_url"]),
        str(profile["api_key"]),
        str(profile["model"]),
    )


def _normalize(
    config: ModelEndpointInput, *, existing_api_key: str = ""
) -> ModelEndpointInput:
    name = _normalize_name(config.name)
    base_url = config.base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ModelConfigurationError("base_url 必须是有效的 HTTP/HTTPS 地址")
    if parsed.username or parsed.password:
        raise ModelConfigurationError("base_url 不能包含认证信息")
    api_key = _clean_api_key(config.api_key) or existing_api_key
    model = config.model.strip()
    if not api_key:
        raise ModelConfigurationError("api_key 不能为空")
    if not model:
        raise ModelConfigurationError("model 不能为空")
    if any(
        len(value) > limit
        for value, limit in (
            (name, 100),
            (base_url, 500),
            (api_key, 2000),
            (model, 200),
        )
    ):
        raise ModelConfigurationError("模型配置字段长度超出允许范围")
    if any(
        "\n" in value or "\r" in value for value in (name, base_url, api_key, model)
    ):
        raise ModelConfigurationError("模型配置字段不能包含换行符")
    return ModelEndpointInput(name, base_url, api_key, model)


def _normalize_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ModelConfigurationError("档案名称不能为空")
    if len(name) > 100 or "\n" in name or "\r" in name:
        raise ModelConfigurationError("档案名称不合法")
    return name


def _is_ready(config: ModelEndpointInput) -> bool:
    return bool(config.base_url and config.api_key and config.model)


def _env_updates(kind: ConfigurationKind, config: ModelEndpointInput) -> dict[str, str]:
    prefix = "LEARNING_LLM" if kind == "llm" else "LEARNING_RAG"
    model_key = "MODEL" if kind == "llm" else "EMBEDDING_MODEL"
    return {
        f"{prefix}_API_BASE": config.base_url,
        f"{prefix}_API_KEY": config.api_key,
        f"{prefix}_{model_key}": config.model,
    }


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


def _write_env(path: Path, updates: dict[str, str]) -> str:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    _validate_env_text(original)
    existing = original.splitlines()
    remaining = dict(updates)
    output = []
    for line in existing:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        output.append(f"{key}={remaining.pop(key)}" if key in remaining else line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    candidate = "\n".join(output) + "\n"
    _validate_env_text(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(f"{path.name}.model-config.backup")
    backup.write_text(original, encoding="utf-8")
    path.write_text(candidate, encoding="utf-8")
    persisted = path.read_text(encoding="utf-8")
    _validate_env_text(persisted)
    values = _read_env(path)
    if any(values.get(key) != value for key, value in updates.items()):
        _restore_env(path, original)
        raise ModelConfigurationError("模型配置写入后校验失败，已恢复原 .env")
    return original


def _restore_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _validate_env_text(content: str) -> None:
    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ModelConfigurationError(
                f".env 第 {line_number} 行不是有效的 KEY=VALUE 配置"
            )
        key = stripped.split("=", 1)[0].strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ModelConfigurationError(f".env 第 {line_number} 行的键名不兼容")


def _clean_api_key(value: str) -> str:
    cleaned = value.strip()
    return "" if "请在UI" in cleaned or "YOUR" in cleaned else cleaned


def _post_request(url: str, **kwargs):
    import requests

    return requests.post(url, **kwargs)


def _apply_runtime_model(kind: ConfigurationKind, config: ModelEndpointInput) -> None:
    if kind == "llm":
        from ktem.llms.manager import llms

        _upsert_model(
            llms,
            "learning-llm",
            {
                "__type__": "kotaemon.llms.ChatOpenAI",
                "temperature": 0.3,
                "base_url": config.base_url,
                "api_key": config.api_key,
                "model": config.model,
                "timeout": 60,
            },
        )
        return
    from ktem.embeddings.manager import embedding_models_manager

    _upsert_model(
        embedding_models_manager,
        "learning-rag",
        {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": config.base_url,
            "api_key": config.api_key,
            "model": config.model,
            "timeout": 30,
        },
    )


def _upsert_model(manager, name: str, spec: dict) -> None:
    if name in manager.info():
        manager.update(name, spec=spec, default=True)
    else:
        manager.add(name, spec=spec, default=True)

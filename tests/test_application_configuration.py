from __future__ import annotations

import pytest

from learning_ext.application.configuration import (
    ModelConfigurationError,
    ModelConfigurationService,
    ModelEndpointInput,
)


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def endpoint(name: str, base_url: str, api_key: str, model: str) -> ModelEndpointInput:
    return ModelEndpointInput(name, base_url, api_key, model)


def test_llm_and_rag_save_independently_preserve_legacy_env(tmp_path):
    env_path = tmp_path / ".env"
    profiles_path = tmp_path / "model_profiles.json"
    env_path.write_text(
        "UNCHANGED=yes\nOPENAI_API_KEY=legacy-key\nOPENAI_CHAT_MODEL=legacy-chat\n",
        encoding="utf-8",
    )
    runtime_calls = []
    service = ModelConfigurationService(
        env_path=env_path,
        profiles_path=profiles_path,
        runtime_apply=lambda kind, config: runtime_calls.append((kind, config)),
    )

    initial = service.get_status()
    llm_id = initial.llm.active_profile_id
    rag_id = initial.rag.active_profile_id
    assert llm_id and rag_id
    service.save(
        "llm",
        llm_id,
        endpoint("主 LLM", "https://llm.example/v1", "llm-key", "chat-test"),
    )
    service.save(
        "rag",
        rag_id,
        endpoint("主 RAG", "https://rag.example/v1", "rag-key", "embed-test"),
    )

    stored = env_path.read_text(encoding="utf-8")
    backup = env_path.with_name(".env.model-config.backup").read_text(encoding="utf-8")
    assert "UNCHANGED=yes" in stored
    assert "OPENAI_API_KEY=legacy-key" in stored
    assert "LEARNING_LLM_API_BASE=https://llm.example/v1" in stored
    assert "LEARNING_LLM_API_KEY=llm-key" in stored
    assert "LEARNING_RAG_API_BASE=https://rag.example/v1" in stored
    assert "LEARNING_RAG_API_KEY=rag-key" in stored
    assert "LEARNING_LLM_API_BASE=https://llm.example/v1" in backup
    assert [kind for kind, _ in runtime_calls] == ["llm", "rag"]
    status = service.get_status()
    assert status.llm.model == "chat-test"
    assert status.rag.model == "embed-test"
    assert "api_key" not in status.to_dict()["llm"]
    assert "llm-key" not in str(status.to_dict())
    assert "rag-key" not in str(status.to_dict())


def test_profiles_can_be_created_switched_and_deleted_without_cross_overwrite(tmp_path):
    env_path = tmp_path / ".env"
    profiles_path = tmp_path / "model_profiles.json"
    calls = []
    service = ModelConfigurationService(
        env_path=env_path,
        profiles_path=profiles_path,
        runtime_apply=lambda kind, config: calls.append((kind, config.model)),
    )
    initial = service.get_status()
    rag_id = initial.rag.active_profile_id
    legacy_llm_id = initial.llm.active_profile_id
    assert rag_id and legacy_llm_id
    service.save(
        "rag",
        rag_id,
        endpoint("资料库", "https://rag.example/v1", "rag-key", "embed-a"),
    )
    service.save(
        "llm",
        legacy_llm_id,
        endpoint("默认 LLM", "https://legacy.example/v1", "legacy-key", "legacy-model"),
    )
    created = service.create_profile("llm", "本地模型")
    llm_id = created.llm.active_profile_id
    assert llm_id and created.llm.active_profile_name == "本地模型"
    service.save(
        "llm",
        llm_id,
        endpoint("本地模型", "http://localhost:11434/v1", "ollama", "qwen3"),
    )
    switched = service.activate("rag", rag_id)
    assert switched.llm.model == "qwen3"
    assert switched.rag.model == "embed-a"
    after_delete = service.delete_profile("llm", llm_id)
    assert after_delete.llm.active_profile_id == "legacy-llm"
    assert after_delete.llm.model == "legacy-model"
    assert calls == [
        ("rag", "embed-a"),
        ("llm", "legacy-model"),
        ("llm", "qwen3"),
        ("rag", "embed-a"),
        ("llm", "legacy-model"),
    ]


def test_last_profile_cannot_be_deleted_and_invalid_env_is_not_overwritten(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("BROKEN LINE\n", encoding="utf-8")
    service = ModelConfigurationService(
        env_path=env_path,
        profiles_path=tmp_path / "profiles.json",
        runtime_apply=lambda *_args: None,
    )
    profile_id = service.get_status().llm.active_profile_id
    assert profile_id

    with pytest.raises(ModelConfigurationError, match="KEY=VALUE"):
        service.save(
            "llm",
            profile_id,
            endpoint("聊天", "https://example.test/v1", "key", "chat"),
        )

    assert env_path.read_text(encoding="utf-8") == "BROKEN LINE\n"


def test_runtime_failure_restores_env_and_does_not_persist_profile_change(tmp_path):
    env_path = tmp_path / ".env"
    profiles_path = tmp_path / "profiles.json"
    env_path.write_text("UNCHANGED=yes\n", encoding="utf-8")
    service = ModelConfigurationService(
        env_path=env_path,
        profiles_path=profiles_path,
        runtime_apply=lambda *_args: (_ for _ in ()).throw(RuntimeError("运行时失败")),
    )
    profile_id = service.get_status().llm.active_profile_id
    assert profile_id

    with pytest.raises(RuntimeError, match="运行时失败"):
        service.save(
            "llm",
            profile_id,
            endpoint("聊天", "https://example.test/v1", "key", "chat"),
        )

    assert env_path.read_text(encoding="utf-8") == "UNCHANGED=yes\n"
    assert not profiles_path.exists()


def test_connectivity_uses_distinct_openai_compatible_endpoints_without_writing(
    tmp_path,
):
    env_path = tmp_path / ".env"
    calls = []
    service = ModelConfigurationService(
        env_path=env_path,
        profiles_path=tmp_path / "profiles.json",
        runtime_apply=lambda *_args: None,
        requester=lambda *args, **kwargs: (
            calls.append((args, kwargs)) or FakeResponse(200)
        ),
    )

    assert (
        service.test(
            "llm", endpoint("聊天", "https://llm.example/v1", "llm-key", "chat-test")
        ).message
        == "对话模型连接成功"
    )
    assert (
        service.test(
            "rag", endpoint("向量", "https://rag.example/v1", "rag-key", "embed-test")
        ).message
        == "RAG 向量模型连接成功"
    )
    assert calls[0][0][0].endswith("/chat/completions")
    assert calls[1][0][0].endswith("/embeddings")
    assert calls[1][1]["json"] == {"model": "embed-test", "input": "ping"}
    assert not env_path.exists()


def test_llm_client_reads_only_the_dedicated_llm_configuration(monkeypatch, tmp_path):
    from learning_ext.llm import client

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LEARNING_LLM_API_BASE=https://llm.example/v1\n"
        "LEARNING_LLM_API_KEY=llm-key\n"
        "LEARNING_LLM_MODEL=chat-model\n"
        "LEARNING_RAG_API_BASE=https://rag.example/v1\n"
        "LEARNING_RAG_API_KEY=rag-key\n"
        "LEARNING_RAG_EMBEDDING_MODEL=embed-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "_ENV_FILE", env_path)
    client.invalidate_cache()

    config = client._load_config()

    assert config["base_url"] == "https://llm.example/v1"
    assert config["api_key"] == "llm-key"
    assert config["chat_model"] == "chat-model"


def test_route_course_and_quiz_depend_on_the_shared_llm_facade():
    from learning_ext.llm import chat, chat_json
    from learning_ext.path_generator import service as path_generator
    from learning_ext.progress import study
    from learning_ext.quiz import service as quiz

    assert path_generator.chat_json is chat_json
    assert study.chat is chat
    assert quiz.chat_json is chat_json


def test_configuration_rejects_invalid_url_and_newline_before_persistence(tmp_path):
    service = ModelConfigurationService(
        env_path=tmp_path / ".env",
        profiles_path=tmp_path / "profiles.json",
        runtime_apply=lambda *_args: None,
    )

    with pytest.raises(ModelConfigurationError, match="HTTP/HTTPS"):
        service.test("llm", endpoint("聊天", "file:///local", "key", "chat"))
    with pytest.raises(ModelConfigurationError, match="换行符"):
        service.test(
            "rag",
            endpoint("向量", "https://example.test", "key\nINJECTED=yes", "embed"),
        )

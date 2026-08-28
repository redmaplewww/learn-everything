from __future__ import annotations

import pytest

from learning_ext.application.configuration import (
    ModelConfigurationError,
    ModelConfigurationInput,
    ModelConfigurationService,
)


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_save_configuration_is_redacted_and_preserves_other_env_lines(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("UNCHANGED=yes\nOPENAI_CHAT_MODEL=old\n", encoding="utf-8")
    runtime_calls = []
    service = ModelConfigurationService(
        env_path=env_path, runtime_apply=runtime_calls.append
    )

    status = service.save(
        ModelConfigurationInput(
            "https://example.test/v1/", "secret-key", "chat-test", "embed-test"
        )
    )

    assert status.api_key_configured is True
    assert status.rag_ready is True
    assert "api_key" not in status.to_dict()
    assert runtime_calls[0].api_key == "secret-key"
    stored = env_path.read_text(encoding="utf-8")
    assert "UNCHANGED=yes" in stored
    assert "OPENAI_API_KEY=secret-key" in stored


def test_connectivity_test_does_not_write_env(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("UNCHANGED=yes\n", encoding="utf-8")
    calls = []
    service = ModelConfigurationService(
        env_path=env_path,
        runtime_apply=lambda _config: None,
        requester=lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse(200),
    )

    result = service.test(
        ModelConfigurationInput("https://example.test/v1", "test-key", "chat-test")
    )

    assert result.ok is True
    assert calls[0][0][0].endswith("/chat/completions")
    assert "test-key" not in env_path.read_text(encoding="utf-8")


def test_configuration_rejects_invalid_base_url(tmp_path):
    service = ModelConfigurationService(
        env_path=tmp_path / ".env", runtime_apply=lambda _config: None
    )

    with pytest.raises(ModelConfigurationError, match="HTTP/HTTPS"):
        service.test(ModelConfigurationInput("file:///local", "key", "chat"))


def test_configuration_rejects_newlines_before_env_write(tmp_path):
    env_path = tmp_path / ".env"
    service = ModelConfigurationService(
        env_path=env_path, runtime_apply=lambda _config: None
    )

    with pytest.raises(ModelConfigurationError, match="换行符"):
        service.save(ModelConfigurationInput("https://example.test", "key\nINJECTED=yes", "chat"))

    assert not env_path.exists()

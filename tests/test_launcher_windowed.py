"""验证窗口模式下没有标准流时，启动器不会因日志或暂停逻辑崩溃。"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import launcher


def test_safe_stream_accepts_missing_console_stream():
    stream = launcher._SafeStream(None)

    assert stream.write("windowed mode") == 0
    assert stream.flush() is None


def test_windowed_mode_uses_null_log_handler(monkeypatch):
    monkeypatch.setattr(launcher.sys, "stdout", None)
    monkeypatch.setattr(launcher.sys, "stderr", None)

    assert isinstance(launcher._create_log_handler(), logging.NullHandler)


def test_pause_before_exit_skips_missing_standard_input(monkeypatch):
    monkeypatch.setattr(launcher.sys, "stdin", None)

    with patch("builtins.input") as prompt:
        launcher.pause_before_exit()

    prompt.assert_not_called()


def test_api_backend_uses_fastapi_entrypoint_and_source_paths(monkeypatch):
    captured = {}
    process = MagicMock(stdout=[])

    def fake_popen(*args, **kwargs):
        captured["args"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        return process

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    launcher.start_api_backend(8012)

    assert captured["args"][1:5] == ["-m", "uvicorn", "api.main:app", "--host"]
    assert captured["args"][-1] == "8012"
    assert captured["cwd"] == str(launcher.BASE_DIR)
    assert str(launcher.BASE_DIR) in captured["env"]["PYTHONPATH"]
    assert str(launcher.KOTAEMON_DIR) in captured["env"]["PYTHONPATH"]
    assert captured["env"]["PYTHONUTF8"] == "1"
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"


def test_frontend_assets_ready_requires_exported_index(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "BASE_DIR", tmp_path)

    assert launcher.frontend_assets_ready() is False

    output = tmp_path / "frontend" / "out"
    output.mkdir(parents=True)
    (output / "index.html").write_text("<main>frontend</main>", encoding="utf-8")

    assert launcher.frontend_assets_ready() is True


def test_wait_for_server_stops_when_process_exits():
    process = MagicMock()
    process.poll.return_value = 1

    assert launcher.wait_for_server(8012, timeout=1, process=process) is False

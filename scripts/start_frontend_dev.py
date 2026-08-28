"""启动 Next.js 与 FastAPI 的本地开发环境。"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
KOTAEMON_DIR = ROOT / "kotaemon"
VENV_PYTHON = KOTAEMON_DIR / ".venv" / "Scripts" / "python.exe"
NEXT_BIN = ROOT / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
API_PORT = 8000
FRONTEND_PORT = 3000
HOST = "127.0.0.1"
LOG_DIR = ROOT / "logs"


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((HOST, port)) != 0


def _wait_for_port(process: subprocess.Popen[str], port: int, timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if not _is_port_free(port):
            return True
        time.sleep(0.2)
    return False


def _forward_output(process: subprocess.Popen[str], label: str, log_path: Path) -> None:
    assert process.stdout is not None
    with log_path.open("a", encoding="utf-8") as log_file:
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            print(f"[{label}] {line}", end="")


def _stop(processes: list[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    python_paths = [str(ROOT), str(KOTAEMON_DIR)]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["HF_HUB_OFFLINE"] = env.get("HF_HUB_OFFLINE", "1")
    env["TRANSFORMERS_OFFLINE"] = env.get("TRANSFORMERS_OFFLINE", "1")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    for key in ("COHERE_API_KEY", "VOYAGE_API_KEY", "MISTRAL_API_KEY", "GOOGLE_API_KEY"):
        env.setdefault(key, "placeholder-key-1234567890")
    env["NEXT_PUBLIC_LEARNING_API_BASE"] = f"http://{HOST}:{API_PORT}/api/v1"
    if env.get("LEARNING_DEV_DATA_DIR"):
        env["THEFLOW_SETTINGS_MODULE"] = "learning_ext.dev_flowsettings"
    else:
        env.pop("THEFLOW_SETTINGS_MODULE", None)
    return env


def main() -> int:
    if not VENV_PYTHON.exists():
        print(f"[错误] 未找到 Kotaemon Python 环境: {VENV_PYTHON}")
        return 1
    if not NEXT_BIN.exists():
        print("[错误] 未找到 Next.js。请先在 frontend 目录执行 npm install。")
        return 1
    node = shutil.which("node")
    if node is None:
        print("[错误] 未找到 Node.js。请安装 Node.js 并确保 node 在 PATH 中。")
        return 1
    occupied = [str(port) for port in (API_PORT, FRONTEND_PORT) if not _is_port_free(port)]
    if occupied:
        print(f"[错误] 端口已被占用: {', '.join(occupied)}。请停止对应服务后重试。")
        return 1

    LOG_DIR.mkdir(exist_ok=True)
    env = _environment()
    api = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "api.main:app", "--host", HOST, "--port", str(API_PORT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    processes = [api]
    threading.Thread(target=_forward_output, args=(api, "api", LOG_DIR / "frontend-dev-api.log"), daemon=True).start()
    if not _wait_for_port(api, API_PORT, timeout=45):
        print("[错误] FastAPI 未能在 45 秒内启动。")
        _stop(processes)
        return 1

    frontend = subprocess.Popen(
        [node, str(NEXT_BIN), "dev", "--port", str(FRONTEND_PORT)],
        cwd=ROOT / "frontend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    processes.append(frontend)
    threading.Thread(target=_forward_output, args=(frontend, "frontend", LOG_DIR / "frontend-dev-next.log"), daemon=True).start()
    if not _wait_for_port(frontend, FRONTEND_PORT, timeout=60):
        print("[错误] Next.js 未能在 60 秒内启动。")
        _stop(processes)
        return 1

    print(f"[OK] 前端: http://{HOST}:{FRONTEND_PORT}")
    print(f"[OK] API: http://{HOST}:{API_PORT}/api/v1/projects")
    print("按 Ctrl+C 停止两个开发服务。")
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在停止开发服务...")
    finally:
        _stop(processes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

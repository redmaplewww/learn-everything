"""学习 Agent - Windows 桌面启动器。

职责：
    1. 定位 Kotaemon venv 和项目根目录
    2. 设置环境变量 (Python 路径、cohere 占位等)
    3. 启动 FastAPI 静态前端服务
    4. 主线程用 PyWebView 打开桌面窗口 (可选，环境无 pywebview 则退化为浏览器)

使用：
    直接双击运行，或被便携版 start.bat / PyInstaller 打包的 exe 调用。
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

class _SafeStream:
    """包装 stdout，遇 GBK 无法编码的字符降级为 ASCII，避免 Windows 控制台崩溃"""

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        if self._stream is None:
            return 0
        try:
            return self._stream.write(text)
        except UnicodeEncodeError:
            return self._stream.write(text.encode("ascii", "replace").decode("ascii"))

    def flush(self):
        if self._stream is not None:
            self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


if sys.stdout is not None:
    sys.stdout = _SafeStream(sys.stdout)
if sys.stderr is not None:
    sys.stderr = _SafeStream(sys.stderr)


def _create_log_handler() -> logging.Handler:
    """窗口模式没有控制台时，避免日志处理器绑定空输出流。"""
    stream = sys.stdout if sys.stdout is not None else sys.stderr
    if stream is None:
        return logging.NullHandler()
    return logging.StreamHandler(stream)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_create_log_handler()],
)
log = logging.getLogger("learning-launcher")

# ------------------------------------------------------------------
# 路径定位 (支持源码运行和 PyInstaller 打包后运行)
# ------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # PyInstaller 打包后：exe 所在目录
    BASE_DIR = Path(sys.executable).parent.resolve()
    _MEIPASS = Path(sys._MEIPASS)  # type: ignore
else:
    BASE_DIR = Path(__file__).parent.resolve()
    _MEIPASS = BASE_DIR

KOTAEMON_DIR = BASE_DIR / "kotaemon"
VENV_PYTHON = KOTAEMON_DIR / ".venv" / "Scripts" / "python.exe"
API_PORT = 8000
HOST = "127.0.0.1"


def is_venv_ready() -> bool:
    return VENV_PYTHON.exists()


def pause_before_exit() -> None:
    """仅在交互式控制台中暂停，避免窗口模式访问空标准输入。"""
    if sys.stdin is not None and sys.stdin.isatty():
        input("按回车键退出...")


def ensure_venv() -> None:
    """检查 venv 是否就绪，否则提示用户运行 setup.bat"""
    if is_venv_ready():
        return
    log.error("=" * 60)
    log.error("Kotaemon 运行环境未就绪！")
    log.error(f"未找到: {VENV_PYTHON}")
    log.error("请先运行 setup.bat 初始化环境 (首次使用需要联网安装依赖)")
    log.error("=" * 60)
    pause_before_exit()
    sys.exit(1)


def find_free_port(default: int = API_PORT) -> int | None:
    """默认端口被占用时，返回后续可用端口。"""
    for port in range(default, default + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return None


def frontend_assets_ready() -> bool:
    return (BASE_DIR / "frontend" / "out" / "index.html").is_file()


def wait_for_server(port: int, timeout: int = 120, process: subprocess.Popen | None = None) -> bool:
    """等待 HTTP 首页可用，并在子进程提前退出时立即返回。"""
    start = time.time()
    while time.time() - start < timeout:
        if process is not None and process.poll() is not None:
            return False
        try:
            with urlopen(f"http://{HOST}:{port}/", timeout=2) as response:
                if response.status == 200:
                    return True
        except (OSError, URLError):
            time.sleep(1)
    return False


def start_api_backend(port: int) -> subprocess.Popen:
    """以子进程启动 FastAPI，并由它托管已导出的 Next.js 静态资源。"""
    env = os.environ.copy()
    for key in ("COHERE_API_KEY", "VOYAGE_API_KEY", "MISTRAL_API_KEY", "GOOGLE_API_KEY"):
        env.setdefault(key, "placeholder-key-1234567890")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BASE_DIR), str(KOTAEMON_DIR), env.get("PYTHONPATH", "")]
    )
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    command = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        HOST,
        "--port",
        str(port),
    ]
    log.info("启动 FastAPI 静态前端服务: %s", " ".join(command))
    proc = subprocess.Popen(
        command,
        cwd=str(BASE_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def _log_pipe():
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    log.info("[api] %s", line)
        except Exception:
            pass

    threading.Thread(target=_log_pipe, daemon=True).start()
    return proc


def open_desktop_window(url: str) -> bool:
    """尝试用 PyWebView 打开桌面窗口，失败则降级到浏览器。

    Returns:
        True 如果用了桌面窗口 (主线程会被 pywebview 阻塞)
        False 如果降级到浏览器
    """
    try:
        import webview  # type: ignore

        log.info("使用 PyWebView 桌面窗口模式")
        webview.create_window(
            title="学习 Agent",
            url=url,
            width=1280,
            height=860,
            min_size=(1024, 700),
        )
        webview.start()
        return True
    except ImportError:
        log.info("未安装 pywebview，降级为浏览器模式")
        return False
    except Exception as e:
        log.warning(f"PyWebView 启动失败 ({e})，降级为浏览器模式")
        return False


def main():
    log.info("=" * 60)
    log.info("学习 Agent - 启动中")
    log.info("=" * 60)

    ensure_venv()

    if not frontend_assets_ready():
        log.error("未找到 frontend/out/index.html，无法启动新前端。请先在 frontend 目录执行 npm run build。")
        pause_before_exit()
        sys.exit(1)
    port = find_free_port(API_PORT)
    if port is None:
        log.error(f"端口 {API_PORT}-{API_PORT + 19} 均被占用，未启动服务。")
        pause_before_exit()
        sys.exit(1)
    if port != API_PORT:
        log.warning(f"端口 {API_PORT} 被占用，改用 {port}")

    proc = start_api_backend(port)
    mode_name = "FastAPI 静态前端服务"
    log.info(f"等待{mode_name}就绪 (最多 180s)...")
    if not wait_for_server(port, timeout=180, process=proc):
        log.error(f"{mode_name}未能就绪或已提前退出，请查看上方日志")
        proc.terminate()
        pause_before_exit()
        sys.exit(1)

    url = f"http://{HOST}:{port}"
    log.info(f"[OK] {mode_name}就绪: {url}")

    # 默认浏览器模式 (最稳定), 设 LE_DESKTOP=1 环境变量启用 PyWebView 桌面窗口
    use_pywebview = os.environ.get("LE_DESKTOP") == "1"

    if use_pywebview:
        if not open_desktop_window(url):
            webbrowser.open(url)
            log.info("PyWebView 不可用，已在浏览器打开。")
            try:
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
        log.info("桌面窗口已关闭，正在停止后端...")
    else:
        webbrowser.open(url)
        log.info(f"已在浏览器打开 ({url})。关闭本窗口或 Ctrl+C 退出。")
        try:
            proc.wait()
        except KeyboardInterrupt:
            pass

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.info("已退出")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception(f"启动失败: {e}")
        pause_before_exit()
        sys.exit(1)

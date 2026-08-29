"""启动入口的静态回归测试。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_start_bat_runs_frontend_development_orchestrator():
    content = (ROOT / "start.bat").read_text(encoding="utf-8")

    assert 'if exist "%~dp0python\\python.exe"' in content
    assert '"%~dp0python\\python.exe" "%~dp0launcher.py"' in content
    assert '"%~dp0scripts\\start_frontend_dev.py"' in content
    assert 'set "PYTHONUTF8=1"' in content


def test_start_bat_is_the_only_application_startup_script():
    assert not (ROOT / "run.bat").exists()

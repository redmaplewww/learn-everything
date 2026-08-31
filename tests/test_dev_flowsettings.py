"""浏览器开发隔离配置测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_development_settings_use_explicit_isolated_data_dir(tmp_path):
    environment = os.environ.copy()
    environment["THEFLOW_SETTINGS_MODULE"] = "learning_ext.dev_flowsettings"
    environment["LEARNING_DEV_DATA_DIR"] = str(tmp_path / "isolated-data")
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "kotaemon"), environment.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from theflow.settings import settings; print(settings.KH_DATABASE)",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )

    expected = (tmp_path / "isolated-data" / "user_data" / "sql.db").resolve()
    assert Path(result.stdout.strip().removeprefix("sqlite:///")) == expected

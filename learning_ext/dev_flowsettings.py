"""浏览器开发用的隔离 Kotaemon 配置。"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
_base_path = ROOT / "kotaemon" / "flowsettings.py"
_spec = importlib.util.spec_from_file_location("_kotaemon_flowsettings", _base_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"无法加载 Kotaemon 配置: {_base_path}")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

for _name in dir(_base):
    if _name.isupper():
        globals()[_name] = getattr(_base, _name)


_data_dir = Path(
    os.environ.get("LEARNING_DEV_DATA_DIR", str(ROOT / ".tmp" / "manual-app-data"))
).resolve()
KH_APP_DATA_DIR = _data_dir
KH_APP_DATA_EXISTS = _data_dir.exists()
KH_USER_DATA_DIR = _data_dir / "user_data"
KH_MARKDOWN_OUTPUT_DIR = _data_dir / "markdown_cache_dir"
KH_CHUNKS_OUTPUT_DIR = _data_dir / "chunks_cache_dir"
KH_ZIP_OUTPUT_DIR = _data_dir / "zip_cache_dir"
KH_ZIP_INPUT_DIR = _data_dir / "zip_cache_dir_in"
KH_DATABASE = f"sqlite:///{KH_USER_DATA_DIR / 'sql.db'}"
KH_FILESTORAGE_PATH = str(KH_USER_DATA_DIR / "files")
KH_DOCSTORE = {
    "__type__": "kotaemon.storages.LanceDBDocumentStore",
    "path": str(KH_USER_DATA_DIR / "docstore"),
}
KH_VECTORSTORE = {
    "__type__": "kotaemon.storages.ChromaVectorStore",
    "path": str(KH_USER_DATA_DIR / "vectorstore"),
}

for _path in (
    KH_APP_DATA_DIR,
    KH_USER_DATA_DIR,
    KH_MARKDOWN_OUTPUT_DIR,
    KH_CHUNKS_OUTPUT_DIR,
    KH_ZIP_OUTPUT_DIR,
    KH_ZIP_INPUT_DIR,
):
    Path(_path).mkdir(parents=True, exist_ok=True)

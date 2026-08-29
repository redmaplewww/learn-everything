"""初始化 learning_ext 模块。

在 Kotaemon 启动时调用，确保：
    1. 学习相关数据表已创建 (复用 Kotaemon engine)
    2. fsrs 库可用
    3. 注册学习特化的 reasoning pipeline (可选)
"""

import logging

logger = logging.getLogger(__name__)
_initialized = False


def _ensure_sqlite_columns(engine) -> None:
    """Backfill columns added after existing local SQLite databases were created."""
    if engine.dialect.name != "sqlite":
        return

    from sqlalchemy import inspect, text

    migrations = {
        "le_card": {
            "step": "INTEGER NOT NULL DEFAULT 0",
            "due_order": "INTEGER NOT NULL DEFAULT 0",
            "suspended": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "le_knode": {
            "collection_ids": "VARCHAR NOT NULL DEFAULT ''",
        },
        "le_note": {
            "selection": "VARCHAR NOT NULL DEFAULT ''",
        },
        "le_resource": {
            "preview": "VARCHAR NOT NULL DEFAULT ''",
            "source": "VARCHAR NOT NULL DEFAULT 'ai'",
        },
    }
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in migrations.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column, ddl in columns.items():
                if column not in existing:
                    conn.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}')
                    )
                    logger.info("[learning_ext] 已补齐 %s.%s", table, column)


def init_learning_ext() -> None:
    """初始化学习特化模块 (幂等，可多次调用)。"""
    global _initialized
    if _initialized:
        return

    try:
        from sqlmodel import SQLModel
        import learning_ext.db.models  # noqa: F401  触发模型注册
        from ktem.db.engine import engine

        SQLModel.metadata.create_all(engine)
        _ensure_sqlite_columns(engine)
        logger.info("[learning_ext] 数据表已就绪")
    except Exception as e:
        logger.warning(f"[learning_ext] 数据表创建失败 (将在首次使用时重试): {e}")

    try:
        import fsrs  # noqa: F401

        logger.info("[learning_ext] fsrs 库可用")
    except ImportError:
        logger.warning(
            "[learning_ext] fsrs 库未安装，复习功能不可用。请在容器内: uv pip install fsrs"
        )

    try:
        from learning_ext.application.configuration import ModelConfigurationService

        ModelConfigurationService().apply_active_profiles()
        logger.info("[learning_ext] 已应用活动 LLM 与 RAG 模型档案")
    except Exception as error:
        logger.warning("[learning_ext] 活动模型档案未应用: %s", error)

    _initialized = True
    logger.info("[learning_ext] 初始化完成")

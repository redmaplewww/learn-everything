"""pytest 全局配置：路径注入 + 共享 fixtures。"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pytest

# 项目根 (learn-everything/)
ROOT = Path(__file__).resolve().parent.parent
KOTAEMON = ROOT / "kotaemon"

# 注入 import 路径
sys.path.insert(0, str(ROOT))  # learning_ext
sys.path.insert(0, str(KOTAEMON))  # kotaemon / ktem / flowsettings

# 占位环境变量，避免 cohere/voyage 等初始化崩溃
for k in ("COHERE_API_KEY", "VOYAGE_API_KEY", "MISTRAL_API_KEY", "GOOGLE_API_KEY"):
    os.environ.setdefault(k, "placeholder-test-key")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


# ============== Session-scoped DB ==============
@pytest.fixture(scope="session")
def _db_engine():
    from sqlmodel import SQLModel

    tmp = Path(tempfile.mkdtemp(prefix="le_test_")) / "test.db"
    db_url = f"sqlite:///{tmp}"
    os.environ["KH_DATABASE"] = db_url

    import learning_ext.db.models  # noqa: F401

    from sqlalchemy.engine import create_engine as _create

    eng = _create(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    yield eng
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass


# ============== Function-scoped session with cleanup ==============
@pytest.fixture
def session(_db_engine) -> Iterator:
    from sqlmodel import Session, text

    with Session(_db_engine) as s:
        yield s
        for table in [
            "le_reviewlog",
            "le_card",
            "le_quiz_attempt",
            "le_quiz_question",
            "le_quiz",
            "le_resource",
            "le_note",
            "le_progress",
            "le_task",
            "le_kedge",
            "le_knode",
            "le_project",
            "le_daily_report",
        ]:
            try:
                s.exec(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        s.commit()


# ============== Mock LLM ==============
@pytest.fixture
def mock_llm(monkeypatch):
    def _fake_chat(
        prompt,
        *,
        system=None,
        model_name=None,
        temperature=0.3,
        stream=False,
        max_tokens=None,
    ):
        if stream:
            return iter(["模拟", "回复"])
        return "这是模拟的 LLM 回复。"

    def _fake_chat_json(prompt, *, system=None, model_name=None):
        import json as _json

        sys_p = system or ""
        if "学习路线" in prompt or (
            "知识点" in prompt[:100] and "prerequisites" in (sys_p + prompt)
        ):
            return {
                "summary": "测试路线",
                "stages": [{"name": "基础", "stage": "base", "goal": "打底"}],
                "nodes": [
                    {
                        "code": "1.1",
                        "title": "入门概念",
                        "description": "基础",
                        "stage": "base",
                        "est_hours": 2.0,
                        "difficulty": 2,
                        "prerequisites": [],
                    },
                    {
                        "code": "1.2",
                        "title": "进阶概念",
                        "description": "进阶",
                        "stage": "base",
                        "est_hours": 3.0,
                        "difficulty": 3,
                        "prerequisites": ["1.1"],
                    },
                    {
                        "code": "2.1",
                        "title": "实战",
                        "description": "练手",
                        "stage": "strengthen",
                        "est_hours": 4.0,
                        "difficulty": 4,
                        "prerequisites": ["1.2"],
                    },
                ],
            }
        if "现有路线 JSON" in prompt:
            return {
                "summary": "已调整的测试路线",
                "stages": [{"name": "基础", "stage": "base", "goal": "打底"}],
                "nodes": [
                    {
                        "code": "1.1",
                        "title": "调整后概念",
                        "description": "调整后的基础",
                        "stage": "base",
                        "est_hours": 2.0,
                        "difficulty": 2,
                        "prerequisites": [],
                    }
                ],
            }
        if "卡片" in prompt:
            return {
                "cards": [
                    {"front": "什么是 X", "back": "X 是...", "card_type": "basic"},
                    {"front": "Y 的定义", "back": "Y 指...", "card_type": "concept"},
                ]
            }
        if "测验题" in prompt or "出" in prompt[:10]:
            return [
                {
                    "qtype": "choice",
                    "stem": "题1?",
                    "options": ["A", "B", "C", "D"],
                    "answer": "A",
                    "explanation": "因为",
                    "difficulty": 3,
                }
            ]
        if (
            "判断对错" in prompt
            or "is_correct" in prompt.lower()
            or "阅卷" in (sys_p + prompt)
        ):
            return {"is_correct": True, "feedback": "答对了"}
        if "winget" in (sys_p or ""):
            return [{"cmd": "echo hello", "desc": "测试命令", "danger": "low"}]
        return {"ok": True}

    import learning_ext.llm.client as llm_client
    import learning_ext.path_generator.service as path_svc
    import learning_ext.quiz.service as quiz_svc
    import learning_ext.progress.study as study_svc
    import learning_ext.practice.auto_setup as auto_svc
    import learning_ext.llm as llm_pkg

    monkeypatch.setattr(llm_client, "chat", _fake_chat)
    monkeypatch.setattr(llm_client, "chat_json", _fake_chat_json)
    monkeypatch.setattr(llm_pkg, "chat", _fake_chat)
    monkeypatch.setattr(llm_pkg, "chat_json", _fake_chat_json)
    monkeypatch.setattr(path_svc, "chat_json", _fake_chat_json)
    monkeypatch.setattr(quiz_svc, "chat_json", _fake_chat_json)
    monkeypatch.setattr(study_svc, "chat", _fake_chat)
    monkeypatch.setattr(auto_svc, "chat_json", _fake_chat_json)
    # fsrs 的 generate_cards_from_node 内部 import chat_json, patch 模块属性会因 attr 不存在而失败
    # 直接 patch learning_ext.llm 的入口即可
    import learning_ext.fsrs_review.service as fsrs_svc

    if hasattr(fsrs_svc, "chat_json"):
        monkeypatch.setattr(fsrs_svc, "chat_json", _fake_chat_json)


# ============== Sample project ==============
@pytest.fixture
def sample_project(session, mock_llm):
    from learning_ext.path_generator import save_roadmap, generate_roadmap

    roadmap = generate_roadmap("测试主题", "无背景", "测试目标", 10)
    project = save_roadmap(
        session,
        user_id="default",
        topic="测试主题",
        background="无背景",
        goal="测试目标",
        weekly_hours=10,
        roadmap=roadmap,
    )
    return project

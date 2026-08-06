"""路线生成 service 测试。"""

from __future__ import annotations

import json

import pytest
from sqlmodel import select

from learning_ext.db.models import KnowledgeEdge, KnowledgeNode, LearningProject
from learning_ext.path_generator import (
    export_roadmap_bundle,
    generate_roadmap,
    import_builtin_roadmap,
    import_roadmap_bundle,
    list_builtin_roadmaps,
    load_builtin_roadmap_bundle,
    load_roadmap,
    refine_roadmap,
    save_roadmap,
)


class TestGenerateRoadmap:
    def test_returns_dict_with_required_keys(self, mock_llm):
        r = generate_roadmap("学Python", "", "", 10)
        assert isinstance(r, dict)
        assert "nodes" in r
        assert "stages" in r
        assert len(r["nodes"]) >= 2

    def test_empty_topic_still_works(self, mock_llm):
        # 不应崩溃 (LLM 处理空输入)
        r = generate_roadmap("", "", "", 5)
        assert isinstance(r, dict)


class TestSaveRoadmap:
    def test_persists_project_and_nodes(self, session, mock_llm):
        roadmap = generate_roadmap("测试", "", "", 10)
        project = save_roadmap(
            session,
            user_id="default",
            topic="测试",
            background="",
            goal="",
            weekly_hours=10,
            roadmap=roadmap,
        )
        assert project.id is not None
        assert project.topic == "测试"
        assert project.user_id == "default"
        assert project.status == "active"

        # 节点应入库
        nodes = session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == project.id)
        ).all()
        assert len(nodes) == len(roadmap["nodes"])
        # 每个节点初始状态是 pending, 掌握度 0
        for n in nodes:
            assert n.status == "pending"
            assert n.mastery == 0.0

    def test_persists_edges(self, session, mock_llm):
        roadmap = generate_roadmap("测试", "", "", 10)
        # mock 返回 1.2 依赖 1.1, 2.1 依赖 1.2
        project = save_roadmap(
            session,
            user_id="default",
            topic="测试",
            background="",
            goal="",
            weekly_hours=10,
            roadmap=roadmap,
        )
        edges = session.exec(
            select(KnowledgeEdge).where(KnowledgeEdge.project_id == project.id)
        ).all()
        # 应有 2 条边 (1.2->1.1, 2.1->1.2)
        assert len(edges) == 2

    def test_self_dependency_ignored(self, session, mock_llm):
        # 如果 LLM 返回自引用依赖, 应跳过
        roadmap = {
            "summary": "测试",
            "stages": [],
            "nodes": [
                {
                    "code": "1.1",
                    "title": "A",
                    "description": "",
                    "stage": "base",
                    "est_hours": 1,
                    "difficulty": 1,
                    "prerequisites": ["1.1"],  # 自引用
                }
            ],
        }
        project = save_roadmap(
            session,
            user_id="default",
            topic="t",
            background="",
            goal="",
            weekly_hours=1,
            roadmap=roadmap,
        )
        edges = session.exec(
            select(KnowledgeEdge).where(KnowledgeEdge.project_id == project.id)
        ).all()
        assert len(edges) == 0

    def test_nonexistent_prerequisite_skipped(self, session):
        # 引用不存在的 code 应跳过, 不崩溃
        roadmap = {
            "summary": "x",
            "stages": [],
            "nodes": [
                {
                    "code": "1.1",
                    "title": "A",
                    "description": "",
                    "stage": "base",
                    "est_hours": 1,
                    "difficulty": 1,
                    "prerequisites": ["9.9"],  # 不存在
                }
            ],
        }
        project = save_roadmap(
            session,
            user_id="default",
            topic="t",
            background="",
            goal="",
            weekly_hours=1,
            roadmap=roadmap,
        )
        edges = session.exec(
            select(KnowledgeEdge).where(KnowledgeEdge.project_id == project.id)
        ).all()
        assert len(edges) == 0

    def test_title_fallback_to_topic(self, session):
        roadmap = {"summary": "", "stages": [], "nodes": []}
        project = save_roadmap(
            session,
            user_id="default",
            topic="我的主题",
            background="",
            goal="",
            weekly_hours=1,
            roadmap=roadmap,
        )
        # summary 为空时应 fallback 到 topic
        assert project.title == "我的主题"


class TestLoadRoadmap:
    def test_reconstructs_with_latest_status(self, session, mock_llm):
        roadmap = generate_roadmap("测试", "", "", 10)
        project = save_roadmap(
            session,
            user_id="default",
            topic="测试",
            background="",
            goal="",
            weekly_hours=10,
            roadmap=roadmap,
        )
        # 修改一个节点状态
        node = session.exec(
            select(KnowledgeNode)
            .where(KnowledgeNode.project_id == project.id)
            .where(KnowledgeNode.code == "1.1")
        ).first()
        node.status = "mastered"
        node.mastery = 0.95
        session.add(node)
        session.commit()

        loaded = load_roadmap(session, project.id)
        n11 = [n for n in loaded["nodes"] if n["code"] == "1.1"][0]
        assert n11["status"] == "mastered"
        assert n11["mastery"] == 0.95

    def test_prerequisites_round_trip(self, session, mock_llm):
        roadmap = generate_roadmap("测试", "", "", 10)
        project = save_roadmap(
            session,
            user_id="default",
            topic="测试",
            background="",
            goal="",
            weekly_hours=10,
            roadmap=roadmap,
        )
        loaded = load_roadmap(session, project.id)
        n12 = [n for n in loaded["nodes"] if n["code"] == "1.2"][0]
        assert "1.1" in n12["prerequisites"]

    def test_load_nonexistent_raises(self, session):
        with pytest.raises(ValueError, match="not found"):
            load_roadmap(session, 99999)


class TestRoadmapImportExport:
    def test_export_bundle_is_formatted_and_importable(self, session, mock_llm):
        roadmap = generate_roadmap("LM Studio 实战", "会 Python", "做本地 AI 助手", 8)
        project = save_roadmap(
            session,
            user_id="default",
            topic="LM Studio 实战",
            background="会 Python",
            goal="做本地 AI 助手",
            weekly_hours=8,
            roadmap=roadmap,
        )

        payload = export_roadmap_bundle(session, project.id)
        data = json.loads(payload)

        assert payload.endswith("\n")
        assert data["kind"] == "learn-everything.roadmap"
        assert data["schema_version"] == 1
        assert data["project"]["topic"] == "LM Studio 实战"
        assert data["project"]["goal"] == "做本地 AI 助手"
        assert data["roadmap"]["nodes"][0]["code"] == "1.1"

        imported = import_roadmap_bundle(session, payload, user_id="default")
        assert imported.id != project.id
        assert imported.topic == "LM Studio 实战"
        imported_roadmap = load_roadmap(session, imported.id)
        assert [n["code"] for n in imported_roadmap["nodes"]] == [
            n["code"] for n in roadmap["nodes"]
        ]

    def test_import_bundle_rejects_malformed_route(self, session):
        with pytest.raises(ValueError, match="nodes"):
            import_roadmap_bundle(
                session,
                json.dumps(
                    {
                        "kind": "learn-everything.roadmap",
                        "schema_version": 1,
                        "project": {"topic": "坏数据"},
                        "roadmap": {"summary": "坏数据"},
                    }
                ),
            )


class TestBuiltinRoadmaps:
    def test_ai_agent_builtin_route_is_valid(self):
        routes = list_builtin_roadmaps()
        route = next(
            r
            for r in routes
            if r["id"] == "ai_agent_systems_opencode_deepreason"
        )

        assert route["nodes"] == 26
        assert route["total_hours"] == 80.0

        bundle = load_builtin_roadmap_bundle(route["id"])
        assert bundle["kind"] == "learn-everything.roadmap"
        assert bundle["project"]["title"].startswith("AI Agent 系统实战路线")

        roadmap = bundle["roadmap"]
        nodes = roadmap["nodes"]
        codes = {node["code"] for node in nodes}
        assert len(nodes) == 26
        assert sum(float(node["est_hours"]) for node in nodes) == 80.0
        assert all(stage.get("goal") for stage in roadmap["stages"])
        assert all(
            prereq in codes
            for node in nodes
            for prereq in node.get("prerequisites", [])
        )

    def test_import_builtin_route_creates_project(self, session):
        project = import_builtin_roadmap(
            session,
            "ai_agent_systems_opencode_deepreason",
            user_id="default",
        )

        assert project.title.startswith("AI Agent 系统实战路线")
        imported = load_roadmap(session, project.id)
        assert len(imported["nodes"]) == 26
        assert imported["nodes"][0]["title"] == "AI Agent 与 Chatbot 的区别"


class TestRefineRoadmap:
    def test_returns_new_roadmap(self, mock_llm):
        current = {"summary": "old", "nodes": [{"code": "1.1", "title": "x"}]}
        refined = refine_roadmap(current, "增加内容")
        assert isinstance(refined, dict)

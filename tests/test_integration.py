"""端到端集成测试：模拟用户完整学习旅程。

覆盖真实用户行为序列：
    1. 生成学习路线
    2. 保存项目 (自动生成教学内容 + 环境清单)
    3. 进学习工作台, 按依赖顺序逐个掌握知识点
    4. 标记已掌握后, 验证后续节点解锁
    5. 为掌握的节点生成复习卡片
    6. 复习卡片 (Again/Hard/Good/Easy 各一次)
    7. 做测验, 验证掌握度更新
    8. 查看项目进度, 验证数据一致
    9. 导出 Markdown 报告
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from learning_ext.db.models import (
    Card,
    KnowledgeNode,
    QuizAttempt,
    QuizQuestion,
    ReviewLog,
    Task,
)
from learning_ext.exporter import (
    export_learning_plan_docx,
    export_markdown,
    export_progress_report,
)
from learning_ext.fsrs_review import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    generate_cards_from_node,
    get_due_cards,
    get_review_stats,
    review_card,
)
from learning_ext.path_generator import generate_roadmap, load_roadmap, save_roadmap
from learning_ext.practice.auto_setup import generate_install_commands
from learning_ext.progress.study import (
    STATUS_LEARNING,
    STATUS_MASTERED,
    generate_env_checklist,
    generate_node_summary,
    get_next_learnable_nodes,
    get_project_progress,
    save_env_tasks,
    set_node_status,
)
from learning_ext.quiz import generate_quiz, grade_answer


class TestUserJourney:
    """模拟一个真实用户从零到完成的学习全过程。"""

    def test_full_learning_journey(self, session, mock_llm):
        # ============ 阶段 1: 用户输入选题, 生成路线 ============
        roadmap = generate_roadmap(
            topic="从零学 Python",
            background="完全零基础",
            goal="能写简单脚本",
            weekly_hours=8,
        )
        assert len(roadmap["nodes"]) == 3  # mock 返回 3 节点
        assert roadmap["nodes"][0]["code"] == "1.1"

        # ============ 阶段 2: 保存项目 ============
        project = save_roadmap(
            session,
            user_id="default",
            topic="从零学 Python",
            background="完全零基础",
            goal="能写简单脚本",
            weekly_hours=8,
            roadmap=roadmap,
        )
        assert project.id is not None

        # ============ 阶段 3: 系统自动生成环境清单 ============
        env_md = generate_env_checklist("从零学 Python", "完全零基础")
        assert len(env_md) > 0
        save_env_tasks(session, project.id, env_md)
        env_task = session.exec(
            select(Task)
            .where(Task.project_id == project.id)
            .where(Task.task_type == "env")
        ).first()
        assert env_task is not None
        assert env_task.status == "pending"

        # ============ 阶段 4: AI 把环境清单转成可执行命令 ============
        commands = generate_install_commands(env_md, "完全零基础")
        assert isinstance(commands, list)

        # ============ 阶段 5: 进工作台, 初始只有 1.1 可学 ============
        learnable = get_next_learnable_nodes(session, project.id)
        assert len(learnable) == 1
        assert learnable[0].code == "1.1"

        # ============ 阶段 6: 为 1.1 生成教学内容 + 复习卡片 ============
        node_11 = learnable[0]
        summary = generate_node_summary(node_11, "从零学 Python")
        assert len(summary) > 0
        # 更新到 DB (模拟工作台保存教学内容)
        node_11.description = summary
        session.add(node_11)
        session.commit()

        cards = generate_cards_from_node(
            session,
            node_11.id,
            "default",
            summary,
            count=3,
        )
        assert len(cards) >= 1

        # ============ 阶段 7: 标记 1.1 为学习中 ============
        set_node_status(session, node_11.id, STATUS_LEARNING)
        learnable = get_next_learnable_nodes(session, project.id)
        assert node_11.id in {n.id for n in learnable}  # 学习中的仍在列表

        # ============ 阶段 8: 复习 1.1 的卡片 (4 种评分各一次) ============
        for card in cards[:1]:  # 只测第一张卡的多次评分
            for rating in [RATING_GOOD, RATING_AGAIN, RATING_HARD, RATING_EASY]:
                reviewed = review_card(session, card.id, rating, "default")
                assert reviewed.reps > 0
        # 验证复习日志
        logs = session.exec(
            select(ReviewLog).where(ReviewLog.card_id == cards[0].id)
        ).all()
        assert len(logs) == 4

        # ============ 阶段 9: 标记 1.1 已掌握, 1.2 应解锁 ============
        set_node_status(session, node_11.id, STATUS_MASTERED)
        learnable = get_next_learnable_nodes(session, project.id)
        codes = {n.code for n in learnable}
        assert "1.2" in codes
        assert "2.1" not in codes  # 2.1 还锁着

        # ============ 阶段 10: 继续 1.2, 然后 2.1, 全部掌握 ============
        for code in ["1.2", "2.1"]:
            node = session.exec(
                select(KnowledgeNode)
                .where(KnowledgeNode.project_id == project.id)
                .where(KnowledgeNode.code == code)
            ).first()
            set_node_status(session, node.id, STATUS_MASTERED)

        # ============ 阶段 11: 全部掌握后, 可学列表应空 ============
        learnable = get_next_learnable_nodes(session, project.id)
        assert len(learnable) == 0

        # ============ 阶段 12: 做一次测验 ============
        nodes = session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == project.id)
        ).all()
        quiz = generate_quiz(
            session,
            "default",
            [n.id for n in nodes],
            project_id=project.id,
            count=2,
        )
        questions = session.exec(
            select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
        ).all()
        assert len(questions) >= 1

        # 答题
        for q in questions:
            grade_answer(session, q.id, "我的回答", "default")
        attempts = session.exec(select(QuizAttempt)).all()
        assert len(attempts) == len(questions)

        # ============ 阶段 13: 查看进度 ============
        prog = get_project_progress(session, project.id)
        assert prog["total"] == 3
        assert prog["done"] == 3
        assert prog["pct"] == 100.0

        # ============ 阶段 14: 复习统计 ============
        stats = get_review_stats(session, user_id="default")
        assert stats["total_cards"] >= 1
        assert stats["due_count"] >= 0  # 可能已过期或未到期

        # ============ 阶段 15: 导出 Markdown 报告 ============
        report = export_markdown(session, project.id)
        assert "从零学 Python" in report
        assert "1.1" in report
        assert "100%" in report  # 完成度

        # ============ 阶段 16: 加载路线, 状态应持久 ============
        loaded = load_roadmap(session, project.id)
        for n in loaded["nodes"]:
            assert n["status"] == STATUS_MASTERED


class TestConcurrencyAndEdgeCases:
    """边界情况和并发场景。"""

    def test_save_same_roadmap_twice_creates_two_projects(self, session, mock_llm):
        """同一选题保存两次应创建两个独立项目 (当前设计)。"""
        roadmap = generate_roadmap("重复测试", "", "", 5)
        p1 = save_roadmap(session, "default", "重复测试", "", "", 5, roadmap)
        p2 = save_roadmap(session, "default", "重复测试", "", "", 5, roadmap)
        assert p1.id != p2.id
        # 两个项目的节点互不干扰
        n1 = session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == p1.id)
        ).all()
        n2 = session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == p2.id)
        ).all()
        assert len(n1) == len(n2) == 3

    def test_orphan_card_no_node(self, session, sample_project):
        """卡片没有关联节点的情况 (边界)。"""
        card = Card(
            user_id="default",
            node_id=None,
            project_id=sample_project.id,
            front="独立问题",
            back="独立答案",
        )
        session.add(card)
        session.commit()
        # 复习应正常工作
        reviewed = review_card(session, card.id, RATING_GOOD, "default")
        assert reviewed.reps == 1

    def test_master_node_then_revert_to_learning(self, session, sample_project):
        """已掌握的节点改回学习中 (用户重新复习)。"""
        node = session.exec(select(KnowledgeNode)).first()
        set_node_status(session, node.id, STATUS_MASTERED)
        set_node_status(session, node.id, STATUS_LEARNING)
        prog = get_project_progress(session, sample_project.id)
        assert prog["done"] == 0  # 改回后不再算 done

    def test_review_rating_boundary_values(self, session, sample_project):
        """评分边界 1 和 4 都应有效。"""
        from learning_ext.db.models import KnowledgeNode

        node = session.exec(select(KnowledgeNode)).first()
        for r in [1, 4]:
            c = Card(
                user_id="default",
                node_id=node.id,
                project_id=node.project_id,
                front=f"Q{r}",
                back="A",
            )
            session.add(c)
            session.commit()
            session.refresh(c)
            reviewed = review_card(session, c.id, r, "default")
            assert reviewed.state in (1, 2, 3)


class TestExport:
    """导出功能测试。"""

    def test_export_markdown_empty_project(self, session):
        from learning_ext.db.models import LearningProject

        p = LearningProject(
            user_id="default",
            topic="空",
            background="",
            goal="",
            weekly_hours=1,
            roadmap_json="{}",
            status="active",
        )
        session.add(p)
        session.commit()
        report = export_markdown(session, p.id)
        assert isinstance(report, str)
        assert "空" in report

    def test_export_markdown_with_cards(self, session, sample_project):
        from learning_ext.db.models import KnowledgeNode

        node = session.exec(select(KnowledgeNode)).first()
        session.add(
            Card(
                user_id="default",
                node_id=node.id,
                project_id=sample_project.id,
                front="Q",
                back="A",
            )
        )
        session.commit()
        report = export_markdown(session, sample_project.id)
        assert "Q" in report  # 卡片内容应在报告中

    def test_exports_sort_decimal_course_codes_numerically(self, session):
        roadmap = {
            "summary": "Decimal export order",
            "stages": [{"name": "Strengthen", "stage": "strengthen", "goal": ""}],
            "nodes": [
                {
                    "code": "2.10",
                    "title": "Two ten",
                    "description": "Ten",
                    "stage": "strengthen",
                    "est_hours": 1,
                    "difficulty": 2,
                    "prerequisites": [],
                },
                {
                    "code": "2.1",
                    "title": "Two one",
                    "description": "One",
                    "stage": "strengthen",
                    "est_hours": 1,
                    "difficulty": 2,
                    "prerequisites": [],
                },
                {
                    "code": "2.2",
                    "title": "Two two",
                    "description": "Two",
                    "stage": "strengthen",
                    "est_hours": 1,
                    "difficulty": 2,
                    "prerequisites": [],
                },
            ],
        }
        project = save_roadmap(
            session,
            user_id="default",
            topic="decimal order",
            background="",
            goal="",
            weekly_hours=3,
            roadmap=roadmap,
        )

        markdown = export_markdown(session, project.id)
        html = export_progress_report(session, project.id)

        assert (
            markdown.index("[2.1]")
            < markdown.index("[2.2]")
            < markdown.index("[2.10]")
        )
        assert (
            html.index("[2.1]") < html.index("[2.2]") < html.index("[2.10]")
        )

    def test_export_learning_plan_docx_contains_route_content(self, session):
        roadmap = {
            "summary": "AI Agent 系统实战路线",
            "stages": [{"name": "基础阶段", "stage": "base", "goal": "概念打底"}],
            "nodes": [
                {
                    "code": "1.1",
                    "title": "AI Agent 与 Chatbot 的区别",
                    "description": "理解 Agent 的行动能力。",
                    "stage": "base",
                    "est_hours": 2,
                    "difficulty": 2,
                    "prerequisites": [],
                }
            ],
        }
        project = save_roadmap(
            session,
            user_id="default",
            topic="AI Agent",
            background="会 Python",
            goal="做一个 evidence-first research agent",
            weekly_hours=10,
            roadmap=roadmap,
            title="AI Agent 系统实战路线",
        )

        docx_bytes = export_learning_plan_docx(session, project.id)

        assert docx_bytes.startswith(b"PK")
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
            document_xml = zf.read("word/document.xml").decode("utf-8")
        assert "AI Agent 系统实战路线" in document_xml
        assert "基础阶段" in document_xml
        assert "AI Agent 与 Chatbot 的区别" in document_xml


class TestAutoSetup:
    """AI 自动环境配置测试 (不实际执行命令)。"""

    def test_generate_install_commands(self, mock_llm):
        cmds = generate_install_commands("# 测试清单\n- Python", "新手")
        assert isinstance(cmds, list)

    def test_run_all_commands_empty(self):
        """空命令列表的流式执行。"""
        from learning_ext.practice.auto_setup import run_all_commands

        chunks = list(run_all_commands([]))
        assert any("无需" in c or "空" in c for c in chunks)

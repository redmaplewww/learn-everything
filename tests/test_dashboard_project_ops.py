from __future__ import annotations

from sqlmodel import select


def test_seed_demo_learning_data_is_repeatable(session):
    from learning_ext.dashboard.service import build_dashboard_data, seed_demo_learning_data
    from learning_ext.db.models import Card, KnowledgeNode, LearningProject, ProgressRecord

    first = seed_demo_learning_data(session)
    second = seed_demo_learning_data(session)

    projects = session.exec(select(LearningProject)).all()
    nodes = session.exec(select(KnowledgeNode)).all()
    cards = session.exec(select(Card)).all()
    progress = session.exec(select(ProgressRecord)).all()
    summary = build_dashboard_data(session, project_id=second.id)

    assert first.title == "学习看板测试项目"
    assert len(projects) == 1
    assert len(nodes) >= 8
    assert len(cards) >= 6
    assert len(progress) >= 10
    assert summary["metrics"]["total_nodes"] == len(nodes)
    assert summary["metrics"]["mastered_nodes"] >= 2
    assert summary["metrics"]["week_minutes"] > 0


def test_delete_project_cascades_learning_data(session):
    from learning_ext.dashboard.service import seed_demo_learning_data
    from learning_ext.db.models import (
        Card,
        DailyReport,
        KnowledgeEdge,
        KnowledgeNode,
        LearningProject,
        NodeNote,
        NodeResource,
        ProgressRecord,
        Quiz,
        QuizAttempt,
        QuizQuestion,
        ReviewLog,
        Task,
    )
    from learning_ext.project_ops import delete_project

    project = seed_demo_learning_data(session)

    result = delete_project(session, project.id)

    assert result["project_id"] == project.id
    assert result["deleted"]["projects"] == 1
    assert session.get(LearningProject, project.id) is None
    for model in (
        Card,
        DailyReport,
        KnowledgeEdge,
        KnowledgeNode,
        NodeNote,
        NodeResource,
        ProgressRecord,
        Quiz,
        QuizAttempt,
        QuizQuestion,
        ReviewLog,
        Task,
    ):
        assert session.exec(select(model)).all() == []


def test_delete_project_missing_id_raises(session):
    from learning_ext.project_ops import delete_project

    try:
        delete_project(session, 99999)
    except ValueError as exc:
        assert "Project 99999 not found" in str(exc)
    else:
        raise AssertionError("delete_project should reject missing projects")

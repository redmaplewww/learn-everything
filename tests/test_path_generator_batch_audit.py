from __future__ import annotations

from unittest.mock import MagicMock

from sqlmodel import select

from learning_ext.db.models import KnowledgeNode
from learning_ext.path_generator import save_roadmap


def _roadmap(summary: str, title: str) -> dict:
    return {
        "summary": summary,
        "stages": [{"name": "Base", "stage": "base", "goal": "Learn"}],
        "nodes": [
            {
                "code": "1.1",
                "title": title,
                "description": "Initial node",
                "stage": "base",
                "est_hours": 1,
                "difficulty": 1,
                "prerequisites": [],
            }
        ],
    }


def _audited_roadmap(topic: str) -> dict:
    return {
        "summary": f"Audited {topic}",
        "stages": [{"name": "Base", "stage": "base", "goal": "Rebuilt"}],
        "nodes": [
            {
                "code": "1.1",
                "title": f"{topic} rebuilt start",
                "description": "Fresh node",
                "stage": "base",
                "est_hours": 1,
                "difficulty": 1,
                "prerequisites": [],
            },
            {
                "code": "1.2",
                "title": f"{topic} rebuilt practice",
                "description": "Fresh practice",
                "stage": "base",
                "est_hours": 2,
                "difficulty": 2,
                "prerequisites": ["1.1"],
            },
        ],
    }


def test_path_page_blank_batch_audit_rebuilds_all_projects(session, monkeypatch):
    import learning_ext.pages.path_generator as path_page_module
    import learning_ext.progress.study as study_module
    from learning_ext.pages.path_generator import PathGeneratorPage

    first = save_roadmap(
        session,
        user_id="default",
        topic="alpha",
        background="",
        goal="",
        weekly_hours=3,
        roadmap=_roadmap("Alpha", "Old alpha"),
    )
    second = save_roadmap(
        session,
        user_id="default",
        topic="beta",
        background="",
        goal="",
        weekly_hours=3,
        roadmap=_roadmap("Beta", "Old beta"),
    )

    audited_topics: list[str] = []
    regenerated_projects: list[int] = []

    def fake_audit_existing_roadmap(
        roadmap, topic, background, goal, weekly_hours, *, model_name=None
    ):
        audited_topics.append(topic)
        return (
            {"score": 88, "verdict": "ok", "problems": [], "changes": ["rebuilt"]},
            _audited_roadmap(topic),
        )

    monkeypatch.setattr(path_page_module, "engine", session.get_bind())
    monkeypatch.setattr(
        path_page_module, "audit_existing_roadmap", fake_audit_existing_roadmap
    )
    monkeypatch.setattr(study_module, "generate_node_summary_to_db", lambda *_args, **_kwargs: True)

    page = PathGeneratorPage(MagicMock())
    _, roadmap_md, roadmap_json, audit_md, status = page._handle_audit_project("", "REPLACE")

    assert audited_topics == ["alpha", "beta"]
    assert "alpha" in roadmap_md
    assert "beta" in roadmap_md
    assert "projects" in roadmap_json
    assert "rebuilt" in audit_md
    assert str(first.id) in status
    assert str(second.id) in status

    for project in (first, second):
        nodes = session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == project.id)
        ).all()
        assert [node.code for node in sorted(nodes, key=lambda n: n.code)] == [
            "1.1",
            "1.2",
        ]

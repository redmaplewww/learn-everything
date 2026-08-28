"""首批 application 用例测试。"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
import pytest
import time
from sqlmodel import select

from learning_ext.application import (
    cancel_content_preparation,
    NodeNotFoundError,
    audit_node_content,
    audit_project_roadmap,
    ProjectNotFoundError,
    create_project,
    export_project,
    generate_node_content,
    generate_practice_lesson,
    generate_node_resources,
    build_dashboard,
    generate_quiz,
    get_due_cards,
    get_content_preparation,
    get_node_detail,
    generate_roadmap_preview,
    get_project_roadmap,
    get_project_workspace,
    list_projects,
    prepare_project_content,
    resume_content_preparation_jobs,
    retry_content_preparation,
    replace_project_roadmap,
    refine_roadmap_preview,
    update_node_status,
    save_node_note,
    review_fsrs_card,
    submit_quiz_answer,
)
from learning_ext.db.models import Card, KnowledgeNode, NodeNote, NodeResource, Task


def test_list_projects_is_sorted_and_returns_structured_summary(session):
    from learning_ext.db.models import LearningProject

    session.add(LearningProject(user_id="default", title="旧", topic="旧主题"))
    session.commit()
    session.add(LearningProject(user_id="default", title="新", topic="新主题"))
    session.commit()

    projects = list_projects(session)

    assert [project.title for project in projects] == ["新", "旧"]
    assert projects[0].progress["total"] == 0
    assert projects[0].to_dict()["topic"] == "新主题"


def test_list_projects_keeps_user_boundary(session):
    from learning_ext.db.models import LearningProject

    session.add(LearningProject(user_id="other", title="别人的项目", topic="主题"))
    session.commit()

    assert list_projects(session) == []


def test_get_project_roadmap_contains_node_ids(sample_project, session):
    roadmap = get_project_roadmap(session, sample_project.id)

    assert roadmap.project_id == sample_project.id
    assert roadmap.nodes
    assert all(node["id"] is not None for node in roadmap.nodes)
    assert roadmap.nodes[0]["code"] == "1.1"


def test_get_project_roadmap_rejects_unknown_project(session):
    with pytest.raises(ProjectNotFoundError):
        get_project_roadmap(session, 9999)


def test_get_node_detail_reads_existing_data_without_generation(sample_project, session):
    node_id = get_project_roadmap(session, sample_project.id).nodes[0]["id"]

    detail = get_node_detail(session, node_id)

    assert detail.id == node_id
    assert detail.project_id == sample_project.id
    assert detail.resources == []


def test_generate_node_content_reports_skipped_generated_and_failed(
    sample_project, session, monkeypatch
):
    import learning_ext.application.study as study_application

    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    node.description = "有效内容" * 200
    session.add(node)
    session.commit()
    monkeypatch.setattr(
        study_application,
        "generate_node_summary_to_db",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不应生成")),
    )

    assert generate_node_content(session, node.id).status == "skipped"

    monkeypatch.setattr(study_application, "generate_node_summary_to_db", lambda *_args, **_kwargs: False)
    assert generate_node_content(session, node.id, force=True).status == "failed"

    def generated(*_args, **_kwargs):
        node.description = "重新生成后的有效内容" * 200
        session.add(node)
        session.commit()
        return True

    monkeypatch.setattr(study_application, "generate_node_summary_to_db", generated)
    result = generate_node_content(session, node.id, force=True)
    assert result.status == "generated"
    assert result.detail.has_content is True


def test_generate_practice_lesson_reports_explicit_generation_states(
    sample_project, session, monkeypatch
):
    import learning_ext.application.study as study_application

    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    called = []

    def generated(node_id, *_args, **_kwargs):
        called.append(node_id)
        session.add(
            Task(
                project_id=sample_project.id,
                node_id=node_id,
                title="实操课程",
                description="执行步骤",
                task_type="practice",
            )
        )
        session.commit()
        return True

    monkeypatch.setattr(study_application, "generate_practice_lesson_to_db", generated)
    result = generate_practice_lesson(session, node.id)
    assert result.status == "generated"
    assert called == [node.id]
    assert result.detail.practice["description"] == "执行步骤"

    assert generate_practice_lesson(session, node.id).status == "skipped"
    monkeypatch.setattr(study_application, "generate_practice_lesson_to_db", lambda *_args, **_kwargs: False)
    assert generate_practice_lesson(session, node.id, force=True).status == "failed"


def test_generate_node_resources_replaces_ai_resources_and_keeps_manual_ones(
    sample_project, session, monkeypatch
):
    import learning_ext.application.study as study_application

    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    session.add(NodeResource(node_id=node.id, project_id=sample_project.id, title="旧 AI", source="ai"))
    session.add(NodeResource(node_id=node.id, project_id=sample_project.id, title="手工资料", source="manual"))
    session.commit()
    monkeypatch.setattr(
        study_application,
        "generate_resources",
        lambda *_args, **_kwargs: [{"title": "新 AI", "url": "https://example.com"}],
    )

    generated = generate_node_resources(session, node.id)
    assert generated.status == "generated"
    assert [item["title"] for item in generated.detail.resources] == ["手工资料", "新 AI"]

    monkeypatch.setattr(
        study_application,
        "generate_resources",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("资料服务不可用")),
    )
    failed = generate_node_resources(session, node.id)
    assert failed.status == "failed"
    assert "资料服务不可用" in failed.error
    assert len(failed.detail.resources) == 2


def test_save_node_note_creates_and_updates_note(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()

    created = save_node_note(session, node.id, "第一版笔记")
    updated = save_node_note(session, node.id, "第二版笔记")

    assert created.note["content"] == "第一版笔记"
    assert updated.note["content"] == "第二版笔记"
    assert updated.note["id"] == created.note["id"]
    assert updated.detail.note["content"] == "第二版笔记"


def test_get_due_cards_reads_fixed_time_queue_without_mutating_cards(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    fixed_now = datetime(2026, 8, 27, 12, 0, 0)
    due = Card(
        user_id="default",
        node_id=node.id,
        project_id=sample_project.id,
        front="到期问题",
        back="到期答案",
        next_review=fixed_now - timedelta(minutes=1),
    )
    future = Card(
        user_id="default",
        node_id=node.id,
        project_id=sample_project.id,
        front="未来问题",
        back="未来答案",
        next_review=fixed_now + timedelta(minutes=1),
    )
    session.add_all([due, future])
    session.commit()

    result = get_due_cards(session, project_id=sample_project.id, now=fixed_now)

    assert [card.front for card in result.cards] == ["到期问题"]
    assert result.cards[0].next_review == due.next_review
    assert session.get(Card, due.id).reps == 0


def test_get_due_cards_returns_empty_queue_and_validates_input(sample_project, session):
    fixed_now = datetime(2026, 8, 27, 12, 0, 0)

    assert get_due_cards(session, project_id=sample_project.id, now=fixed_now).cards == []
    with pytest.raises(ValueError, match="limit"):
        get_due_cards(session, limit=0, now=fixed_now)


def test_review_fsrs_card_returns_schedule_and_next_card(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    first = Card(
        user_id="default",
        node_id=node.id,
        project_id=sample_project.id,
        front="第一张",
        back="答案一",
        next_review=datetime.utcnow() - timedelta(minutes=2),
    )
    second = Card(
        user_id="default",
        node_id=node.id,
        project_id=sample_project.id,
        front="第二张",
        back="答案二",
        next_review=datetime.utcnow() - timedelta(minutes=1),
    )
    session.add_all([first, second])
    session.commit()

    result = review_fsrs_card(session, first.id, 3, project_id=sample_project.id)

    assert result.card.id == first.id
    assert result.card.reps == 1
    assert result.card.next_review > datetime.utcnow() - timedelta(minutes=1)
    assert result.next_card is not None
    assert result.next_card.id == second.id


def test_review_fsrs_card_rejects_invalid_card_scope_and_rating(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    foreign = Card(
        user_id="other",
        node_id=node.id,
        project_id=sample_project.id,
        front="其他用户",
        back="答案",
    )
    session.add(foreign)
    session.commit()

    with pytest.raises(ValueError, match="不存在"):
        review_fsrs_card(session, 9999, 3)
    with pytest.raises(ValueError, match="当前用户"):
        review_fsrs_card(session, foreign.id, 3)
    with pytest.raises(ValueError, match="rating"):
        review_fsrs_card(session, foreign.id, 0, user_id="other")


def test_generate_quiz_returns_project_scoped_question_dtos(sample_project, session, mock_llm):
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).all()[:2]

    result = generate_quiz(
        session, sample_project.id, [node.id for node in nodes], count=2, qtype="mixed"
    )

    assert result.project_id == sample_project.id
    assert result.questions
    assert all(question.node_id in {node.id for node in nodes} for question in result.questions)
    with pytest.raises(NodeNotFoundError):
        generate_quiz(session, sample_project.id, [9999])


def test_submit_quiz_answer_returns_feedback_and_mastery(sample_project, session, mock_llm):
    node = session.exec(select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)).first()
    quiz = generate_quiz(session, sample_project.id, [node.id], count=1)

    result = submit_quiz_answer(session, quiz.questions[0].id, "模拟答案")

    assert result.is_correct is True
    assert result.feedback
    assert result.node_id == node.id
    assert result.mastery is not None
    with pytest.raises(ValueError, match="答案不能为空"):
        submit_quiz_answer(session, quiz.questions[0].id, " ")


def test_build_dashboard_returns_structured_project_data(sample_project, session):
    result = build_dashboard(session, sample_project.id)

    assert result.project_id == sample_project.id
    assert result.metrics["total_nodes"] > 0
    assert len(result.heatmap) == 14
    assert all(isinstance(project["id"], int) for project in result.projects)


def test_content_audits_return_proposals_without_persisting(sample_project, session, monkeypatch):
    import learning_ext.application.roadmap as roadmap_application
    import learning_ext.application.study as study_application

    node = session.exec(select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)).first()
    original_description = node.description
    original_roadmap = sample_project.roadmap_json
    monkeypatch.setattr(study_application, "audit_node_content_service", lambda *_args: "节点审计报告")
    monkeypatch.setattr(
        roadmap_application,
        "audit_existing_roadmap",
        lambda *_args: ({"score": 80}, {"summary": "建议路线", "nodes": []}),
    )

    node_audit = audit_node_content(session, node.id)
    project_audit = audit_project_roadmap(session, sample_project.id)

    assert node_audit.report == "节点审计报告"
    assert project_audit.proposed_roadmap["summary"] == "建议路线"
    session.expire_all()
    assert session.get(KnowledgeNode, node.id).description == original_description
    assert session.get(type(sample_project), sample_project.id).roadmap_json == original_roadmap


def test_export_project_preserves_content_types_and_filenames(sample_project, session):
    expected = {
        "roadmap": ("learning_route_", ".json", "application/json"),
        "markdown": ("learning_notes_", ".md", "text/markdown"),
        "report": ("learning_report_", ".html", "text/html"),
        "anki": ("learning_cards_", ".zip", "application/zip"),
    }

    for kind, (prefix, suffix, media_type) in expected.items():
        exported = export_project(session, sample_project.id, kind)
        assert exported.filename.startswith(prefix)
        assert exported.filename.endswith(suffix)
        assert exported.media_type.startswith(media_type)
        assert exported.content

    with pytest.raises(ValueError, match="不支持"):
        export_project(session, sample_project.id, "pdf")


def test_workspace_aggregates_nodes_without_generation(sample_project, session):
    node = session.exec(
        select(KnowledgeNode)
        .where(KnowledgeNode.project_id == sample_project.id)
        .order_by(KnowledgeNode.id)
    ).first()
    assert node is not None
    node.description = "x" * 500
    session.add(Task(project_id=sample_project.id, title="环境", task_type="env"))
    session.add(Task(project_id=sample_project.id, node_id=node.id, title="实操", task_type="practice", description="做实验"))
    session.add(NodeNote(node_id=node.id, project_id=sample_project.id, content="我的笔记"))
    session.add(NodeResource(node_id=node.id, project_id=sample_project.id, title="文档", url="https://example.com"))
    session.commit()

    workspace = get_project_workspace(session, sample_project.id)

    assert workspace.project["id"] == sample_project.id
    assert workspace.nodes[0].has_content is True
    assert workspace.nodes[0].practice["title"] == "实操"
    assert workspace.nodes[0].note["content"] == "我的笔记"
    assert workspace.nodes[0].resources[0]["title"] == "文档"
    assert workspace.environment["status"] == "pending"


def test_workspace_rejects_unknown_project(session):
    with pytest.raises(ProjectNotFoundError):
        get_project_workspace(session, 9999)


def test_workspace_supports_project_without_nodes(session):
    from learning_ext.db.models import LearningProject

    project = LearningProject(user_id="default", title="空项目", topic="主题")
    session.add(project)
    session.commit()

    workspace = get_project_workspace(session, project.id)

    assert workspace.nodes == []
    assert workspace.progress["total"] == 0


def test_update_node_status_returns_refreshed_workspace(sample_project, session):
    node = session.exec(select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)).first()
    result = update_node_status(session, node.id, "learning")

    assert result.node["status"] == "learning"
    assert result.workspace.nodes[0].status == "learning"


def test_update_node_status_rejects_invalid_or_unknown_node(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    with pytest.raises(ValueError):
        update_node_status(session, node.id, "invalid")
    with pytest.raises(NodeNotFoundError):
        update_node_status(session, 9999, "learning")


def test_generate_roadmap_preview_audits_without_persisting(session, monkeypatch):
    import learning_ext.application.roadmap as roadmap_application

    generated = {"summary": "初版", "nodes": [{"code": "1.1", "title": "基础"}]}
    audited = {"summary": "审计后", "nodes": generated["nodes"], "_audit": {"score": 91}}
    monkeypatch.setattr(roadmap_application, "generate_roadmap", lambda *args, **kwargs: generated)
    monkeypatch.setattr(roadmap_application, "audit_and_rewrite_roadmap", lambda *args, **kwargs: audited.copy())

    result = generate_roadmap_preview("主题", "", "目标", 8)

    assert result.roadmap["summary"] == "审计后"
    assert result.audit == {"score": 91}
    assert list_projects(session) == []


def test_generate_roadmap_preview_logs_request_context(session, monkeypatch, caplog):
    import learning_ext.application.roadmap as roadmap_application
    from learning_ext.observability import reset_request_id, set_request_id

    monkeypatch.setattr(
        roadmap_application,
        "generate_roadmap",
        lambda *_args, **_kwargs: {"summary": "初版", "nodes": [{"code": "1.1"}]},
    )
    monkeypatch.setattr(
        roadmap_application,
        "audit_and_rewrite_roadmap",
        lambda *_args, **_kwargs: {
            "summary": "审计后",
            "nodes": [{"code": "1.1"}],
            "_audit": {"score": 88},
        },
    )
    caplog.set_level("INFO", logger="uvicorn.error")
    token = set_request_id("preview-log-123")
    try:
        generate_roadmap_preview("测试主题", "", "", 8)
    finally:
        reset_request_id(token)

    messages = [record.getMessage() for record in caplog.records]
    assert any("路线预览开始 request_id=preview-log-123" in message for message in messages)
    assert any("路线预览完成 request_id=preview-log-123" in message for message in messages)


def test_refine_roadmap_preview_validates_input_and_returns_service_result(monkeypatch):
    import learning_ext.application.roadmap as roadmap_application

    monkeypatch.setattr(
        roadmap_application,
        "refine_roadmap_service",
        lambda roadmap, instruction, **kwargs: {**roadmap, "summary": instruction},
    )

    assert refine_roadmap_preview({"nodes": [{"code": "1.1"}]}, "补充实践")["summary"] == "补充实践"
    with pytest.raises(ValueError):
        refine_roadmap_preview({}, "补充实践")
    with pytest.raises(ValueError):
        refine_roadmap_preview({"nodes": [{"code": "1.1"}]}, " ")


def test_create_project_persists_project_and_environment_task(session, monkeypatch):
    import learning_ext.application.roadmap as roadmap_application

    monkeypatch.setattr(roadmap_application, "generate_env_checklist", lambda *args, **kwargs: "环境清单")
    roadmap = {"summary": "路线", "nodes": [{"code": "1.1", "title": "节点"}]}

    result = create_project(session, "主题", "背景", "目标", 6, roadmap)

    assert result.environment_status == "ready"
    assert result.node_count == 1
    assert get_project_workspace(session, result.project_id).environment["description"] == "环境清单"


def test_create_project_keeps_saved_project_when_environment_fails(session, monkeypatch):
    import learning_ext.application.roadmap as roadmap_application

    monkeypatch.setattr(
        roadmap_application,
        "generate_env_checklist",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("环境服务不可用")),
    )
    roadmap = {"summary": "路线", "nodes": [{"code": "1.1", "title": "节点"}]}

    result = create_project(session, "主题", "", "", 6, roadmap)

    assert result.environment_status == "failed"
    assert "环境服务不可用" in result.environment_error
    assert get_project_roadmap(session, result.project_id).nodes


def test_prepare_project_content_records_generated_and_failed_nodes(sample_project, session, monkeypatch):
    import learning_ext.progress.study as study

    node_ids = [node["id"] for node in get_project_roadmap(session, sample_project.id).nodes]
    monkeypatch.setattr(
        study,
        "generate_node_summary_to_db",
        lambda node_id, *_args, **_kwargs: node_id != node_ids[1],
    )

    result = prepare_project_content(session, sample_project.id, initial_count=3)
    stored = get_content_preparation(session, result.job_id)

    assert result.status == "blocked"
    assert result.generated_node_ids == [node_ids[0], node_ids[2]]
    assert result.failed_node_ids == [node_ids[1]]
    assert result.pending_node_ids == []
    assert stored == result


def test_prepare_project_content_exposes_background_progress(sample_project, session, monkeypatch):
    import learning_ext.progress.study as study

    monkeypatch.setattr(study, "generate_node_summary_to_db", lambda *_args, **_kwargs: True)

    result = prepare_project_content(session, sample_project.id, initial_count=0)

    assert result.status == "doing"
    assert result.pending_node_ids
    for _ in range(20):
        stored = get_content_preparation(session, result.job_id)
        if stored.status != "doing":
            break
        time.sleep(0.05)
    assert stored.status == "done"
    assert stored.pending_node_ids == []


def test_content_preparation_can_cancel_and_retry_pending_nodes(
    sample_project, session, monkeypatch
):
    import learning_ext.progress.study as study

    started = threading.Event()
    release = threading.Event()

    def slow_generate(*_args, **_kwargs):
        started.set()
        assert release.wait(timeout=2)
        return True

    monkeypatch.setattr(study, "generate_node_summary_to_db", slow_generate)
    started_job = prepare_project_content(session, sample_project.id, initial_count=0)
    assert started.wait(timeout=1)

    cancelling = cancel_content_preparation(session, sample_project.id, started_job.job_id)
    assert cancelling.status == "cancelling"
    assert cancelling.cancel_requested is True

    release.set()
    for _ in range(40):
        cancelled = get_content_preparation(session, started_job.job_id)
        if cancelled.status == "cancelled":
            break
        time.sleep(0.05)
    assert cancelled.status == "cancelled"
    assert cancelled.pending_node_ids

    monkeypatch.setattr(study, "generate_node_summary_to_db", lambda *_args, **_kwargs: True)
    retried = retry_content_preparation(session, sample_project.id, started_job.job_id)
    assert retried.status == "doing"
    assert retried.attempts == 2
    for _ in range(40):
        completed = get_content_preparation(session, started_job.job_id)
        if completed.status != "doing":
            break
        time.sleep(0.05)
    assert completed.status == "done"
    assert completed.pending_node_ids == []
    assert completed.error is None


def test_content_preparation_resumes_interrupted_job(sample_project, session, monkeypatch):
    import learning_ext.progress.study as study

    node_ids = [node["id"] for node in get_project_roadmap(session, sample_project.id).nodes]
    job = Task(
        project_id=sample_project.id,
        title="学习内容准备",
        task_type="content_preparation",
        status="doing",
        output=json.dumps(
            {
                "generated_node_ids": [],
                "failed_node_ids": [],
                "pending_node_ids": node_ids,
                "attempts": 1,
                "error": None,
                "cancel_requested": False,
            }
        ),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    monkeypatch.setattr(study, "generate_node_summary_to_db", lambda *_args, **_kwargs: True)

    assert resume_content_preparation_jobs(session) == 1
    for _ in range(40):
        session.expire_all()
        resumed = get_content_preparation(session, job.id)
        if resumed.status != "doing":
            break
        time.sleep(0.05)
    assert resumed.status == "done"
    assert resumed.generated_node_ids == node_ids


def test_replace_project_roadmap_requires_confirmation_and_prepares_content(
    sample_project, session, monkeypatch
):
    import learning_ext.progress.study as study

    monkeypatch.setattr(study, "generate_node_summary_to_db", lambda *_args, **_kwargs: True)
    replacement = {
        "summary": "替换路线",
        "nodes": [
            {"code": "1.1", "title": "新节点一"},
            {"code": "1.2", "title": "新节点二", "prerequisites": ["1.1"]},
        ],
    }

    with pytest.raises(ValueError, match="必须明确确认"):
        replace_project_roadmap(session, sample_project.id, replacement, confirmed=False)
    result = replace_project_roadmap(session, sample_project.id, replacement, confirmed=True)

    roadmap = get_project_roadmap(session, sample_project.id)
    assert result.previous_node_count == 3
    assert result.new_node_count == 2
    assert result.content_preparation.status == "doing"
    assert [node["title"] for node in roadmap.nodes] == ["新节点一", "新节点二"]

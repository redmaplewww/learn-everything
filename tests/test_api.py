"""首批 FastAPI 契约测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import select

from api.dependencies import get_session
from api.main import create_app
from datetime import datetime, timedelta

from learning_ext.db.models import Card, KnowledgeNode, LearningProject, NodeResource


def api_client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_app_serves_exported_frontend_from_configured_directory(tmp_path):
    (tmp_path / "index.html").write_text("<main>Next.js 静态前端</main>", encoding="utf-8")

    response = TestClient(create_app(frontend_dir=tmp_path)).get("/")

    assert response.status_code == 200
    assert "Next.js 静态前端" in response.text


def test_list_projects_returns_application_order(session):
    session.add(LearningProject(user_id="default", title="旧项目", topic="主题"))
    session.commit()
    session.add(LearningProject(user_id="default", title="新项目", topic="主题"))
    session.commit()

    response = api_client(session).get("/api/v1/projects")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["新项目", "旧项目"]


def test_api_assigns_and_propagates_request_id(session, caplog):
    client = api_client(session)
    caplog.set_level("INFO", logger="uvicorn.error")

    generated = client.get("/api/v1/projects")
    assert generated.status_code == 200
    assert generated.headers["x-request-id"]

    supplied = client.get(
        "/api/v1/projects",
        headers={"x-request-id": "route-check-123"},
    )
    assert supplied.status_code == 200
    assert supplied.headers["x-request-id"] == "route-check-123"
    assert any("request_id=route-check-123" in record.getMessage() for record in caplog.records)


def test_get_project_roadmap_returns_node_ids(sample_project, session):
    response = api_client(session).get(f"/api/v1/projects/{sample_project.id}/roadmap")

    assert response.status_code == 200
    assert response.json()["nodes"][0]["id"] is not None


def test_project_reads_return_not_found(session):
    client = api_client(session)

    assert client.get("/api/v1/projects/999/roadmap").status_code == 404
    assert client.get("/api/v1/projects/999/workspace").status_code == 404


def test_workspace_read_returns_existing_data_without_generation(sample_project, session):
    response = api_client(session).get(f"/api/v1/projects/{sample_project.id}/workspace")

    assert response.status_code == 200
    assert response.json()["project"]["id"] == sample_project.id
    assert response.json()["nodes"]


def test_patch_node_status_persists_and_returns_workspace(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()

    response = api_client(session).patch(
        f"/api/v1/nodes/{node.id}/status", json={"status": "learning"}
    )

    assert response.status_code == 200
    assert response.json()["node"]["status"] == "learning"
    assert response.json()["workspace"]["progress"]["learning"] == 1
    assert session.get(KnowledgeNode, node.id).status == "learning"


def test_patch_node_status_maps_invalid_and_unknown_errors(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    client = api_client(session)

    assert client.patch(
        f"/api/v1/nodes/{node.id}/status", json={"status": "unknown"}
    ).status_code == 400
    assert client.patch("/api/v1/nodes/999/status", json={"status": "learning"}).status_code == 404
    assert client.patch(f"/api/v1/nodes/{node.id}/status", json={}).status_code == 422


def test_preview_roadmap_returns_structured_application_result(mock_llm, session):
    response = api_client(session).post(
        "/api/v1/roadmaps/preview",
        json={
            "topic": "测试主题",
            "background": "有 Python 基础",
            "goal": "完成测试项目",
            "weekly_hours": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["roadmap"]["nodes"]
    assert isinstance(response.json()["audit"], dict)


def test_preview_roadmap_validates_input(session):
    response = api_client(session).post(
        "/api/v1/roadmaps/preview",
        json={"topic": "", "weekly_hours": 0},
    )

    assert response.status_code == 422


def test_refine_roadmap_returns_structured_application_result(mock_llm, session):
    roadmap = {
        "summary": "原路线",
        "stages": [{"name": "基础", "stage": "base", "goal": "打底"}],
        "nodes": [
            {
                "code": "1.1",
                "title": "入门",
                "description": "基础",
                "stage": "base",
                "est_hours": 2,
                "difficulty": 2,
                "prerequisites": [],
            }
        ],
    }

    response = api_client(session).post(
        "/api/v1/roadmaps/refine",
        json={"roadmap": roadmap, "instruction": "增加练习"},
    )

    assert response.status_code == 200
    assert response.json()["roadmap"]["nodes"]


def test_refine_roadmap_rejects_empty_preview(session):
    response = api_client(session).post(
        "/api/v1/roadmaps/refine",
        json={"roadmap": {}, "instruction": "增加练习"},
    )

    assert response.status_code == 400


def test_create_project_and_start_content_preparation(mock_llm, session):
    roadmap = {
        "summary": "待保存路线",
        "stages": [{"name": "基础", "stage": "base", "goal": "打底"}],
        "nodes": [
            {
                "code": "1.1",
                "title": "入门",
                "description": "基础",
                "stage": "base",
                "est_hours": 2,
                "difficulty": 2,
                "prerequisites": [],
            }
        ],
    }
    client = api_client(session)

    created = client.post(
        "/api/v1/projects",
        json={
            "topic": "测试主题",
            "background": "",
            "goal": "完成测试项目",
            "weekly_hours": 8,
            "roadmap": roadmap,
        },
    )

    assert created.status_code == 201
    assert created.json()["node_count"] == 1
    assert created.json()["environment_status"] == "ready"

    project_id = created.json()["project_id"]
    started = client.post(
        f"/api/v1/projects/{project_id}/content-preparation", json={"initial_count": 3}
    )

    assert started.status_code == 202
    assert started.json()["status"] == "done"
    assert started.json()["generated_node_ids"]

    current = client.get(
        f"/api/v1/projects/{project_id}/content-preparation/{started.json()['job_id']}"
    )
    assert current.status_code == 200
    assert current.json()["status"] == "done"


def test_content_preparation_rejects_unknown_project(session):
    response = api_client(session).post(
        "/api/v1/projects/999/content-preparation", json={}
    )

    assert response.status_code == 404


def test_node_detail_read_and_explicit_operations(sample_project, session, monkeypatch):
    import learning_ext.application.study as study_application

    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    client = api_client(session)
    assert client.get(f"/api/v1/nodes/{node.id}").status_code == 200

    monkeypatch.setattr(study_application, "generate_node_summary_to_db", lambda *_args, **_kwargs: False)
    generated = client.post(f"/api/v1/nodes/{node.id}/content", json={"force": True})
    assert generated.status_code == 200
    assert generated.json()["status"] == "failed"

    saved = client.put(f"/api/v1/nodes/{node.id}/note", json={"content": "API 笔记"})
    assert saved.status_code == 200
    assert saved.json()["note"]["content"] == "API 笔记"


def test_review_routes_return_due_queue_and_persist_rating(sample_project, session):
    node = session.exec(select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)).first()
    card = Card(user_id="default", node_id=node.id, project_id=sample_project.id, front="问题", back="答案", next_review=datetime.utcnow() - timedelta(minutes=1))
    session.add(card)
    session.commit()
    client = api_client(session)

    due = client.get(f"/api/v1/reviews/due?project_id={sample_project.id}")
    assert due.status_code == 200
    assert due.json()["cards"][0]["id"] == card.id

    reviewed = client.post(f"/api/v1/reviews/{card.id}", json={"rating": 3, "project_id": sample_project.id})
    assert reviewed.status_code == 200
    assert reviewed.json()["card"]["reps"] == 1


def test_quiz_routes_generate_and_grade(mock_llm, sample_project, session):
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).all()[:2]
    client = api_client(session)

    generated = client.post(
        f"/api/v1/projects/{sample_project.id}/quizzes",
        json={"node_ids": [node.id for node in nodes], "count": 2, "qtype": "mixed"},
    )
    assert generated.status_code == 201
    question = generated.json()["questions"][0]
    assert question["node_id"] in {node.id for node in nodes}

    answered = client.post(
        f"/api/v1/projects/{sample_project.id}/quizzes/questions/{question['id']}/answer",
        json={"answer": "模拟答案"},
    )
    assert answered.status_code == 200
    assert answered.json()["is_correct"] is True


def test_dashboard_and_export_routes_return_application_results(sample_project, session):
    client = api_client(session)

    dashboard = client.get(f"/api/v1/projects/{sample_project.id}/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["metrics"]["total_nodes"] > 0

    exported = client.get(f"/api/v1/projects/{sample_project.id}/exports/roadmap")
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].endswith('.json"')
    assert exported.headers["content-type"].startswith("application/json")


def test_rag_stream_route_encodes_application_events_as_sse(session):
    from api.dependencies import get_rag_gateway
    from learning_ext.adapters.kotaemon_rag import RagStreamEvent, RetrievedExcerpt

    class FakeGateway:
        def stream_answer(self, _request):
            yield RagStreamEvent(
                kind="evidence",
                excerpts=(RetrievedExcerpt(source_id="file-1", text="资料片段"),),
            )
            yield RagStreamEvent(kind="answer_delta", text="回答分片")
            yield RagStreamEvent(kind="complete")

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_rag_gateway] = lambda: FakeGateway()
    response = TestClient(app).post(
        "/api/v1/rag/stream",
        json={
            "collection_id": "1",
            "conversation_id": "conv-1",
            "message": "问题",
            "history": [],
            "file_ids": ["file-1"],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: evidence" in response.text
    assert '"text": "资料片段"' in response.text
    assert "event: answer_delta" in response.text
    assert "event: complete" in response.text


def test_resource_upload_stream_persists_index_status(sample_project, session, tmp_path, monkeypatch):
    from api.dependencies import get_rag_gateway
    from learning_ext.adapters.kotaemon_rag import IndexingEvent, RagCollection

    class FakeGateway:
        def create_collection(self, name):
            return RagCollection(id="collection-7", name=name)

        def index_documents(self, request):
            yield IndexingEvent(kind="progress", path=request.paths[0], message="开始索引")
            yield IndexingEvent(kind="completed", path=request.paths[0], source_id="source-7")

    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    monkeypatch.setenv("LE_UPLOAD_PATH", str(tmp_path / "uploads"))
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_rag_gateway] = lambda: FakeGateway()
    client = TestClient(app)

    response = client.post(
        f"/api/v1/nodes/{node.id}/resources/upload/stream",
        files={"file": ("sample.txt", b"FastAPI delegates to application.", "text/plain")},
    )

    assert response.status_code == 200
    assert "event: started" in response.text
    assert "event: completed" in response.text
    resource = session.exec(
        select(NodeResource).where(NodeResource.node_id == node.id)
    ).first()
    status = client.get(
        f"/api/v1/nodes/{node.id}/resources/{resource.id}/index-status"
    )
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["source_id"] == "source-7"

    resources = client.get(f"/api/v1/nodes/{node.id}/resources")
    assert resources.status_code == 200
    assert resources.json()[0]["source_id"] == "source-7"
    preview = client.get(
        f"/api/v1/nodes/{node.id}/resources/{resource.id}/deletion-preview"
    )
    assert preview.status_code == 200
    assert preview.json()["confirmation_phrase"] == f"删除资料 {resource.id}"


def test_resource_upload_rejects_unsupported_file_type(sample_project, session):
    node = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == sample_project.id)
    ).first()
    client = api_client(session)

    response = client.post(
        f"/api/v1/nodes/{node.id}/resources/upload/stream",
        files={"file": ("unsafe.exe", b"not a document", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "暂只支持" in response.json()["detail"]


def test_model_configuration_routes_never_echo_api_key(session, tmp_path):
    from api.dependencies import get_model_configuration_service
    from learning_ext.application.configuration import ModelConfigurationService

    service = ModelConfigurationService(
        env_path=tmp_path / ".env",
        runtime_apply=lambda _config: None,
        requester=lambda *_args, **_kwargs: type("Response", (), {"status_code": 200})(),
    )
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_model_configuration_service] = lambda: service
    client = TestClient(app)
    payload = {
        "base_url": "https://example.test/v1",
        "api_key": "secret-key",
        "chat_model": "chat-test",
        "embedding_model": "embed-test",
    }

    initial = client.get("/api/v1/model-configuration")
    saved = client.put("/api/v1/model-configuration", json=payload)
    tested = client.post("/api/v1/model-configuration/test", json=payload)

    assert initial.status_code == 200
    assert saved.status_code == 200
    assert saved.json()["api_key_configured"] is True
    assert "secret-key" not in saved.text
    assert "api_key" not in saved.json()
    assert tested.json() == {"ok": True, "message": "对话模型连接成功"}

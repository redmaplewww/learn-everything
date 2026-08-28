from __future__ import annotations

from unittest.mock import MagicMock

from learning_ext.db.models import KnowledgeNode, NodeResource


def test_generate_resources_returns_compact_sources_without_summary(monkeypatch):
    import learning_ext.llm as llm
    import learning_ext.notes.service as notes

    node = KnowledgeNode(
        project_id=1,
        code="2.1",
        title="LoRA 微调",
        description="## LoRA 原理\n这里讲低秩适配。\n\n## 训练流程\n这里讲训练脚本。",
        stage="strengthen",
    )

    monkeypatch.setattr(
        llm,
        "chat_json",
        lambda *_args, **_kwargs: [
            {
                "title": "LoRA paper",
                "url": "https://example.com/lora.pdf",
                "rtype": "pdf",
                "reference_for": "## LoRA 原理",
                "description": "支撑 LoRA 公式和低秩分解说明",
            }
        ],
    )
    monkeypatch.setattr(
        notes,
        "fetch_resource_content",
        lambda *_args, **_kwargs: {
            "ok": True,
            "title": "LoRA paper",
            "url": "https://example.com/lora.pdf",
            "format": "pdf",
            "status": 200,
            "content": "PDF text " * 80,
        },
    )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError("reference resources should not generate a study report")

    monkeypatch.setattr(
        notes,
        "summarize_fetched_resources",
        forbidden_summary,
        raising=False,
    )

    resources = notes.generate_resources(node, "学习大模型微调")

    assert len(resources) == 1
    assert resources[0]["rtype"] == "pdf"
    assert resources[0]["url"] == "https://example.com/lora.pdf"
    assert "参考位置：## LoRA 原理" in resources[0]["description"]
    assert "支撑 LoRA 公式" in resources[0]["description"]
    assert resources[0]["preview"].startswith("PDF text")


def test_fetch_resource_content_decodes_html_with_meta_charset(monkeypatch):
    import learning_ext.notes.service as notes

    body = (
        "<html><head><meta charset=\"gbk\"><title>中文标题</title></head>"
        "<body><main>中文正文" + ("内容" * 140) + "</main></body></html>"
    )
    payload = body.encode("gbk")

    class FakeResponse:
        status_code = 200
        url = "https://example.com/gbk.html"
        headers = {"content-type": "text/html"}
        content = payload
        apparent_encoding = "ISO-8859-1"

        @property
        def text(self):
            return payload.decode("utf-8", errors="replace")

    monkeypatch.setattr(
        "requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    fetched = notes.fetch_resource_content("https://example.com/gbk.html")

    assert fetched["ok"] is True
    assert fetched["title"] == "中文标题"
    assert "中文正文" in fetched["content"]
    assert "�" not in fetched["content"]


def test_fetch_resource_content_prefers_html_meta_over_wrong_header_charset(
    monkeypatch,
):
    import learning_ext.notes.service as notes

    body = (
        "<html><head><meta charset=\"gbk\"><title>中文标题</title></head>"
        "<body><main>中文正文" + ("内容" * 140) + "</main></body></html>"
    )
    payload = body.encode("gbk")

    class FakeResponse:
        status_code = 200
        url = "https://example.com/wrong-header.html"
        headers = {"content-type": "text/html; charset=ISO-8859-1"}
        content = payload
        apparent_encoding = "ISO-8859-1"

    monkeypatch.setattr(
        "requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    fetched = notes.fetch_resource_content("https://example.com/wrong-header.html")

    assert fetched["ok"] is True
    assert fetched["title"] == "中文标题"
    assert "中文正文" in fetched["content"]
    assert "ÖÐÎÄ" not in fetched["content"]


def test_fetch_resource_content_accepts_pdf_resources(monkeypatch):
    import learning_ext.notes.service as notes

    class FakeResponse:
        status_code = 200
        url = "https://example.com/paper.pdf"
        headers = {"content-type": "application/pdf"}
        content = b"%PDF-1.4 fake"

    monkeypatch.setattr(
        "requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    monkeypatch.setattr(
        notes,
        "_extract_pdf_text",
        lambda content, **_kwargs: "PDF 正文内容" * 80,
        raising=False,
    )

    fetched = notes.fetch_resource_content("https://example.com/paper.pdf")

    assert fetched["ok"] is True
    assert fetched["format"] == "pdf"
    assert fetched["title"] == "paper.pdf"
    assert "PDF 正文内容" in fetched["content"]


def test_workbench_resource_rendering_is_compact():
    from learning_ext.pages.study_workbench import StudyWorkbenchPage

    page = StudyWorkbenchPage(MagicMock())
    resource = NodeResource(
        node_id=1,
        project_id=1,
        title="LoRA paper",
        url="https://example.com/lora.pdf",
        rtype="pdf",
        description="参考位置：## LoRA 原理\n说明：支撑 LoRA 公式",
        preview="LONG_EXTRACT " * 300,
        source="ai",
    )

    md = page._render_resources_md([resource])

    assert "LoRA paper" in md
    assert "参考位置：## LoRA 原理" in md
    assert "https://example.com/lora.pdf" in md
    assert "已拉取正文摘录" not in md
    assert "LONG_EXTRACT" not in md


def test_workbench_reference_copy_no_longer_promises_study_report():
    import inspect

    from learning_ext.pages.study_workbench import StudyWorkbenchPage

    source = "\n".join(
        [
            inspect.getsource(StudyWorkbenchPage.on_building_ui),
            inspect.getsource(StudyWorkbenchPage._auto_init),
            inspect.getsource(StudyWorkbenchPage._on_node_select),
            inspect.getsource(StudyWorkbenchPage._ensure_resources_background),
            inspect.getsource(StudyWorkbenchPage._gen_resources),
        ]
    )

    assert "学习汇报" not in source
    assert "拉取并总结资料" not in source
    assert "拉取参考资料" in source


def test_gen_resources_reports_actual_saved_resource_count(monkeypatch):
    from types import SimpleNamespace

    import learning_ext.pages.study_workbench as wb
    from learning_ext.db.models import KnowledgeNode, LearningProject
    from learning_ext.pages.study_workbench import StudyWorkbenchPage

    page = StudyWorkbenchPage(MagicMock())
    node = KnowledgeNode(id=7, project_id=3, code="2.1", title="LoRA")
    project = LearningProject(id=3, title="大模型微调", topic="大模型微调")

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, model, item_id):
            if model is KnowledgeNode:
                return node
            if model is LearningProject:
                return project
            return None

    saved_resources = [
        NodeResource(node_id=7, project_id=3, title="A", rtype="pdf", preview="x"),
        NodeResource(node_id=7, project_id=3, title="B", rtype="html", preview="x"),
    ]

    monkeypatch.setattr(wb, "Session", lambda *_args, **_kwargs: FakeSession())
    monkeypatch.setattr(
        wb,
        "generate_node_resources",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="generated",
            resource_count=len(saved_resources),
            error=None,
            detail=SimpleNamespace(resources=saved_resources),
        ),
    )

    _md, status = page._gen_resources(7, 3)

    assert status == "✅ 已拉取 2 份参考资料"


def test_audit_resource_context_ignores_legacy_summary_resources(monkeypatch):
    from learning_ext.progress import audit

    resources = [
        NodeResource(
            node_id=1,
            project_id=1,
            title="AI 资料学习汇报",
            rtype="summary",
            description="这是一段旧版详细学习汇报",
            preview="",
        ),
        NodeResource(
            node_id=1,
            project_id=1,
            title="LoRA paper",
            url="https://example.com/lora.pdf",
            rtype="pdf",
            description="参考位置：## LoRA 原理",
            preview="PDF 正文" * 200,
        ),
    ]

    monkeypatch.setattr(audit, "get_resources", lambda *_args, **_kwargs: resources)

    context = audit._resource_context(MagicMock(), 1)

    assert "旧版详细学习汇报" not in context
    assert "LoRA paper" in context

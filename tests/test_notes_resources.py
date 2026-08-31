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

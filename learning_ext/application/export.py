"""项目导出的客户端无关用例。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from learning_ext.application.projects import _get_project
from learning_ext.exporter.service import export_anki_apkg, export_markdown, export_progress_report
from learning_ext.path_generator.service import export_roadmap_bundle


@dataclass(frozen=True)
class ProjectExport:
    project_id: int
    kind: str
    filename: str
    media_type: str
    content: bytes


def export_project(
    session: Session,
    project_id: int,
    kind: str,
    *,
    user_id: str = "default",
) -> ProjectExport:
    """导出项目数据，返回可由任意客户端下载的内容和文件元数据。"""
    _get_project(session, project_id, user_id)
    if kind == "roadmap":
        return _text_export(
            project_id, kind, f"learning_route_{project_id}.json", "application/json", export_roadmap_bundle(session, project_id)
        )
    if kind == "markdown":
        return _text_export(
            project_id, kind, f"learning_notes_{project_id}.md", "text/markdown", export_markdown(session, project_id)
        )
    if kind == "report":
        return _text_export(
            project_id, kind, f"learning_report_{project_id}.html", "text/html", export_progress_report(session, project_id)
        )
    if kind == "anki":
        return ProjectExport(
            project_id=project_id,
            kind=kind,
            filename=f"learning_cards_{project_id}.zip",
            media_type="application/zip",
            content=export_anki_apkg(session, project_id),
        )
    raise ValueError("不支持的导出类型")


def _text_export(
    project_id: int, kind: str, filename: str, media_type: str, content: str
) -> ProjectExport:
    return ProjectExport(
        project_id=project_id,
        kind=kind,
        filename=filename,
        media_type=f"{media_type}; charset=utf-8",
        content=content.encode("utf-8"),
    )

"""学习看板的客户端无关用例。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlmodel import Session

from learning_ext.application.projects import _get_project
from learning_ext.dashboard.service import build_dashboard_data


@dataclass(frozen=True)
class Dashboard:
    project_id: int | None
    projects: list[dict[str, Any]]
    metrics: dict[str, float | int]
    status_counts: dict[str, int]
    heatmap: list[dict[str, str | float]]
    latest_report: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_dashboard(
    session: Session,
    project_id: int | None = None,
    *,
    user_id: str = "default",
) -> Dashboard:
    """读取看板数据，不构造 Gradio 或 Plot 对象。"""
    if project_id is not None:
        _get_project(session, project_id, user_id)
    data = build_dashboard_data(session, user_id=user_id, project_id=project_id)
    return Dashboard(
        project_id=data["project_id"],
        projects=[{"label": label, "id": int(value)} for label, value in data["projects"]],
        metrics=data["metrics"],
        status_counts=data["status_counts"],
        heatmap=data["heatmap"],
        latest_report=data["latest_report"],
    )

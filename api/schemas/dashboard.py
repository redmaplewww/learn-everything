"""看板 HTTP Schema。"""

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    project_id: int | None
    projects: list[dict]
    metrics: dict
    status_counts: dict[str, int]
    heatmap: list[dict]
    latest_report: str

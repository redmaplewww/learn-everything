"""看板和项目导出接口。"""

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from api.dependencies import get_session
from api.schemas.dashboard import DashboardResponse
from learning_ext.application import build_dashboard, export_project

router = APIRouter(prefix="/projects/{project_id}", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def read_dashboard(project_id: int, session: Session = Depends(get_session)):
    return build_dashboard(session, project_id).to_dict()


@router.get("/exports/{kind}")
def download_export(kind: str, project_id: int, session: Session = Depends(get_session)):
    exported = export_project(session, project_id, kind)
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )

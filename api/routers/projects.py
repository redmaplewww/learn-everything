"""项目读取接口。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from api.dependencies import get_session
from api.schemas.projects import (
    ContentPreparationRequest,
    ContentPreparationResponse,
    CreateProjectRequest,
    CreateProjectResponse,
    DeleteProjectRequest,
    ProjectDeletionResponse,
    ProjectRoadmapResponse,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectWorkspaceResponse,
    UpdateProjectRequest,
)
from learning_ext.application import (
    cancel_content_preparation,
    create_project,
    delete_project,
    get_content_preparation,
    get_project_roadmap,
    get_project,
    get_project_workspace,
    list_projects,
    prepare_project_content,
    retry_content_preparation,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummaryResponse])
def read_projects(session: Session = Depends(get_session)):
    return [project.to_dict() for project in list_projects(session)]


@router.post("", response_model=CreateProjectResponse, status_code=201)
def create_project_route(
    payload: CreateProjectRequest, session: Session = Depends(get_session)
):
    return create_project(session, **payload.model_dump()).to_dict()


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project_route(
    project_id: int,
    payload: UpdateProjectRequest,
    session: Session = Depends(get_session),
):
    return update_project(session, project_id, **payload.model_dump())


@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(project_id: int, session: Session = Depends(get_session)):
    return get_project(session, project_id)


@router.delete("/{project_id}", response_model=ProjectDeletionResponse)
def delete_project_route(
    project_id: int,
    payload: DeleteProjectRequest,
    session: Session = Depends(get_session),
):
    return delete_project(session, project_id, **payload.model_dump())


@router.get("/{project_id}/roadmap", response_model=ProjectRoadmapResponse)
def read_project_roadmap(
    project_id: int, session: Session = Depends(get_session)
):
    return get_project_roadmap(session, project_id).to_dict()


@router.get("/{project_id}/workspace", response_model=ProjectWorkspaceResponse)
def read_project_workspace(
    project_id: int, session: Session = Depends(get_session)
):
    return get_project_workspace(session, project_id).to_dict()


@router.post(
    "/{project_id}/content-preparation",
    response_model=ContentPreparationResponse,
    status_code=202,
)
def start_content_preparation(
    project_id: int,
    payload: ContentPreparationRequest,
    session: Session = Depends(get_session),
):
    return prepare_project_content(
        session, project_id, initial_count=payload.initial_count
    ).to_dict()


@router.get(
    "/{project_id}/content-preparation/{job_id}",
    response_model=ContentPreparationResponse,
)
def read_content_preparation(
    project_id: int, job_id: int, session: Session = Depends(get_session)
):
    preparation = get_content_preparation(session, job_id)
    if preparation.project_id != project_id:
        raise ValueError("内容准备作业不属于该项目")
    return preparation.to_dict()


@router.post(
    "/{project_id}/content-preparation/{job_id}/cancel",
    response_model=ContentPreparationResponse,
)
def cancel_content_preparation_route(
    project_id: int, job_id: int, session: Session = Depends(get_session)
):
    return cancel_content_preparation(session, project_id, job_id).to_dict()


@router.post(
    "/{project_id}/content-preparation/{job_id}/retry",
    response_model=ContentPreparationResponse,
    status_code=202,
)
def retry_content_preparation_route(
    project_id: int, job_id: int, session: Session = Depends(get_session)
):
    return retry_content_preparation(session, project_id, job_id).to_dict()

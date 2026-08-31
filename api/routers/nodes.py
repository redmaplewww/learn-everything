"""节点写接口。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from api.dependencies import get_session
from api.schemas.nodes import (
    GenerateNodeContentRequest,
    NodeDetailResponse,
    NodeNoteSaveResponse,
    NodeOperationResponse,
    SaveNodeNoteRequest,
    UpdateNodeStatusRequest,
    UpdateNodeStatusResponse,
)
from learning_ext.application import (
    generate_node_content,
    generate_node_resources,
    generate_practice_lesson,
    get_node_detail,
    save_node_note,
    update_node_status,
)

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/{node_id}", response_model=NodeDetailResponse)
def read_node_detail(node_id: int, session: Session = Depends(get_session)):
    return get_node_detail(session, node_id).to_dict()


@router.post("/{node_id}/content", response_model=NodeOperationResponse)
def generate_content(
    node_id: int,
    payload: GenerateNodeContentRequest,
    session: Session = Depends(get_session),
):
    return generate_node_content(session, node_id, force=payload.force).to_dict()


@router.post("/{node_id}/practice", response_model=NodeOperationResponse)
def generate_practice(
    node_id: int,
    payload: GenerateNodeContentRequest,
    session: Session = Depends(get_session),
):
    return generate_practice_lesson(session, node_id, force=payload.force).to_dict()


@router.post("/{node_id}/resources", response_model=NodeOperationResponse)
def generate_resources(node_id: int, session: Session = Depends(get_session)):
    return generate_node_resources(session, node_id).to_dict()


@router.put("/{node_id}/note", response_model=NodeNoteSaveResponse)
def save_note(
    node_id: int,
    payload: SaveNodeNoteRequest,
    session: Session = Depends(get_session),
):
    return save_node_note(session, node_id, payload.content).to_dict()


@router.patch("/{node_id}/status", response_model=UpdateNodeStatusResponse)
def patch_node_status(
    node_id: int,
    payload: UpdateNodeStatusRequest,
    session: Session = Depends(get_session),
):
    return update_node_status(session, node_id, payload.status).to_dict()

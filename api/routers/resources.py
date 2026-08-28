"""节点本地资料上传和索引接口。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from api.dependencies import get_rag_gateway, get_session
from api.schemas.resources import (
    ResourceDeletionRequest,
    ResourceDeletionResponse,
    NodeResourceResponse,
    ResourceDeletionPreviewResponse,
    ResourceIndexStatusResponse,
)
from learning_ext.adapters.kotaemon_rag import KotaemonRagGateway
from learning_ext.application import (
    delete_node_resource,
    get_resource_deletion_preview,
    get_resource_index_status,
    list_node_resources,
    stream_index_node_resource,
)

router = APIRouter(prefix="/nodes", tags=["resources"])

_ALLOWED_SUFFIXES = {".txt", ".md", ".pdf", ".docx", ".html"}
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("/{node_id}/resources/upload/stream")
async def upload_and_index_resource(
    node_id: int,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    gateway: KotaemonRagGateway = Depends(get_rag_gateway),
):
    filename = _validate_filename(file.filename)
    stored_path = await _store_upload(file, filename)

    async def events():
        for event in stream_index_node_resource(
            session,
            gateway,
            node_id=node_id,
            path=stored_path,
            filename=filename,
        ):
            if await request.is_disconnected():
                return
            yield f"event: {event.kind}\ndata: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get(
    "/{node_id}/resources/{resource_id}/index-status",
    response_model=ResourceIndexStatusResponse,
)
def read_resource_index_status(
    node_id: int,
    resource_id: int,
    session: Session = Depends(get_session),
):
    return get_resource_index_status(
        session, node_id=node_id, resource_id=resource_id
    ).to_dict()


@router.get("/{node_id}/resources", response_model=list[NodeResourceResponse])
def read_node_resources(node_id: int, session: Session = Depends(get_session)):
    return [item.to_dict() for item in list_node_resources(session, node_id=node_id)]


@router.get(
    "/{node_id}/resources/{resource_id}/deletion-preview",
    response_model=ResourceDeletionPreviewResponse,
)
def read_resource_deletion_preview(
    node_id: int,
    resource_id: int,
    session: Session = Depends(get_session),
):
    return get_resource_deletion_preview(
        session, node_id=node_id, resource_id=resource_id
    ).to_dict()


@router.delete(
    "/{node_id}/resources/{resource_id}", response_model=ResourceDeletionResponse
)
def delete_resource(
    node_id: int,
    resource_id: int,
    payload: ResourceDeletionRequest,
    session: Session = Depends(get_session),
    gateway: KotaemonRagGateway = Depends(get_rag_gateway),
):
    return delete_node_resource(
        session,
        gateway,
        node_id=node_id,
        resource_id=resource_id,
        confirmation_phrase=payload.confirmation_phrase,
    ).to_dict()


def _validate_filename(raw_filename: str | None) -> str:
    filename = Path(raw_filename or "").name.strip()
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="缺少有效的上传文件名")
    if Path(filename).suffix.lower() not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="暂只支持 TXT、Markdown、PDF、DOCX 和 HTML 文件")
    return filename


async def _store_upload(upload: UploadFile, filename: str) -> Path:
    destination = _upload_root() / f"{uuid4().hex}_{filename}"
    written = 0
    try:
        with destination.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > _MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="上传文件不能超过 20 MB")
                output.write(chunk)
    finally:
        await upload.close()
    return destination


def _upload_root() -> Path:
    configured = os.environ.get("LE_UPLOAD_PATH")
    if configured:
        root = Path(configured)
    else:
        from theflow.settings import settings

        root = Path(settings.KH_FILESTORAGE_PATH) / "learning_uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root

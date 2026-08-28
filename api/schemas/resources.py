"""资料上传与索引状态 HTTP Schema。"""

from pydantic import BaseModel


class ResourceIndexStatusResponse(BaseModel):
    resource_id: int
    node_id: int
    collection_id: str | None
    source_id: str | None
    status: str
    message: str | None


class NodeResourceResponse(BaseModel):
    resource_id: int
    node_id: int
    title: str
    rtype: str
    source: str
    status: str
    message: str | None
    collection_id: str | None
    source_id: str | None


class ResourceDeletionPreviewResponse(BaseModel):
    resource: NodeResourceResponse
    confirmation_phrase: str
    index_delete_required: bool


class ResourceDeletionRequest(BaseModel):
    confirmation_phrase: str


class ResourceDeletionResponse(BaseModel):
    resource_id: int
    node_id: int
    collection_id: str | None
    source_id: str | None
    index_deleted: bool

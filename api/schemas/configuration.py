"""模型配置 HTTP Schema。"""

from pydantic import BaseModel, Field


class ModelEndpointResponse(BaseModel):
    active_profile_id: str | None
    active_profile_name: str | None
    base_url: str
    model: str
    api_key_configured: bool
    ready: bool


class ModelProfileResponse(BaseModel):
    id: str
    name: str
    base_url: str
    model: str
    api_key_configured: bool


class ModelConfigurationResponse(BaseModel):
    llm: ModelEndpointResponse
    rag: ModelEndpointResponse
    llm_profiles: list[ModelProfileResponse]
    rag_profiles: list[ModelProfileResponse]


class ModelEndpointWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(default="", max_length=2000)
    model: str = Field(min_length=1, max_length=200)


class ModelProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ModelConnectivityResponse(BaseModel):
    ok: bool
    message: str

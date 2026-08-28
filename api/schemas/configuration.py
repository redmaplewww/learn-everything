"""必要模型配置 HTTP Schema。"""

from pydantic import BaseModel, Field


class ModelConfigurationResponse(BaseModel):
    base_url: str
    chat_model: str
    embedding_model: str
    api_key_configured: bool
    chat_ready: bool
    rag_ready: bool


class ModelConfigurationWriteRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=2000)
    chat_model: str = Field(min_length=1, max_length=200)
    embedding_model: str = Field(default="", max_length=200)


class ModelConnectivityResponse(BaseModel):
    ok: bool
    message: str

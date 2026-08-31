"""RAG 流式对话请求模型。"""

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=16000)


class RagChatStreamRequest(BaseModel):
    collection_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=16000)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=50)
    file_ids: list[str] = Field(min_length=1, max_length=100)

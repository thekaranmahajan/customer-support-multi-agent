from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    route: str
    citations: list[str] = Field(default_factory=list)
    sql_query: str | None = None
    agent_notes: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    files: list[str]
    indexed_documents: int


class CustomerPreview(BaseModel):
    customer_id: int
    full_name: str
    plan: str
    city: str

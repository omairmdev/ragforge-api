from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: str = Field(
        default="default",
        description="Unique ID for multi-turn conversation memory",
    )


class SourceCitation(BaseModel):
    text: str
    page: int | None = None
    score: float | None = None
    file_name: str | None = None


class UploadResponse(BaseModel):
    file_name: str
    chunks_created: int
    collection: str


class QueryDoneEvent(BaseModel):
    answer: str
    sources: list[SourceCitation] = []
    conversation_id: str

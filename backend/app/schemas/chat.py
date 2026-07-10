from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    extracted_data: dict
    summary: str | None = None
    suggestions: list[str] = []
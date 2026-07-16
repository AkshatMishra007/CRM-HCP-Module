from unittest import result

from fastapi import APIRouter
from app.agent.graph import graph
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/chat",
    tags=["AI Chat"]
)

@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):

    result = graph.invoke(
        {
            "user_input": request.message
        }
    )

    return ChatResponse(
        extracted_data=result["extracted_data"],
        summary=result["summary"],
        suggestions=result["suggestions"]
    )
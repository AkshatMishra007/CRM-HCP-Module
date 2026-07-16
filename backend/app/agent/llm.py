import os
from typing import Any

from app.config import settings


def _load_groq_client() -> Any:
    api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY") or ""
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the repository root .env or backend/.env file."
        )

    try:
        from langchain_groq import ChatGroq
    except Exception as exc:
        raise RuntimeError(
            "Failed to import langchain_groq. Ensure dependencies are installed and the environment allows native extensions. "
            f"Original error: {exc}"
        ) from exc

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=api_key,
        temperature=0,
    )


class LLMClient:
    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is None:
            self._client = _load_groq_client()

    def invoke(self, prompt: str) -> Any:
        self._ensure_client()
        return self._client.invoke(prompt)


llm = LLMClient()
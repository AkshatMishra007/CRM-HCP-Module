import os

from langchain_groq import ChatGroq

from app.config import settings

api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY") or ""
if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Add it to the repository root .env or backend/.env file."
    )

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=api_key,
    temperature=0,
)
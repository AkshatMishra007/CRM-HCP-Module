from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .models import AISuggestion, HCP, Interaction, Material, Sample
from .routers import hcp, interaction, chat
app = FastAPI(title="HCP Interaction API", version="1.0.0")

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database initialization failed: {e}")

app.include_router(hcp.router)
app.include_router(interaction.router)
app.include_router(chat.router)

@app.get("/")
def home():
    return {"message": "Backend API is running successfully"}

@app.get("/health")
def health():
    return {"status": "ok"}

origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
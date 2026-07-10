from fastapi import FastAPI

from .database import Base, engine
from .models import AISuggestion, HCP, Interaction, Material, Sample
from .routers import hcp, interaction,chat
from fastapi.middleware.cors import CORSMiddleware
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
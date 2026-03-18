from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.core.database import init_database


app = FastAPI(
    title="ASR Meeting Assistant",
    description="Backend for meeting transcription, summary, and persistent meeting records.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.upload_dir), name="media")


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.services.auth_service import init_auth_db


# Initialize FastAPI application
app = FastAPI(
    title="ASR Meeting Assistant",
    description="Backend for Meeting transcription, summary, and action item extraction.",
    version="0.1.0",
)

# CORS Configuration
# Allow all origins, methods, and headers for development convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Register API Router
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    init_auth_db()


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Simple health check to verify the service is running.
    """
    return {"status": "ok"}

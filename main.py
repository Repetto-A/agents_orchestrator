from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router, inventory_router
import os

app = FastAPI(
    title="Smart Sales AI",
    description="Multi-agent AI system for sales intelligence",
    version="0.1.0"
)

def _get_allowed_origins() -> list[str]:
    defaults = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    extra = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return list(dict.fromkeys([*defaults, *extra]))

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_origin_regex=r"^https://[a-zA-Z0-9-]+\.up\.railway\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(inventory_router)

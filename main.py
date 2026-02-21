from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router, inventory_router

app = FastAPI(
    title="Smart Sales AI",
    description="Multi-agent AI system for sales intelligence",
    version="0.1.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(inventory_router)

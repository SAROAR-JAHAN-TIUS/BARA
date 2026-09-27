"""
BARA Backend – FastAPI Application Entry Point.
"""
from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analysis import router as analysis_router

app = FastAPI(
    title="BARA – Backend Architecture & API Analyzer",
    description=(
        "BARA analyzes frontend and backend source code to detect "
        "API integration mismatches and visualize application architecture."
    ),
    version="1.0.0",
)

# CORS: allow the Vite dev server and production frontend
origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "BARA"}


app.include_router(analysis_router, prefix="/api")

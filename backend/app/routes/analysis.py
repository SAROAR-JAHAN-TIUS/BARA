"""
BARA Backend – API Routes.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from app.models.analysis import AnalysisRequest, AnalysisResult
from app.services.analysis_service import run_analysis, get_analysis

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest):
    """
    Analyze a project at the given path on the server filesystem.

    Returns a full AnalysisResult including frontend calls, backend endpoints,
    detected issues, and architecture graph.
    """
    try:
        result = run_analysis(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
    return result


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis_result(analysis_id: str):
    """Retrieve a previously computed analysis by its ID."""
    result = get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result

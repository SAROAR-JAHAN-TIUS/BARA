"""
BARA Backend – API Routes.
"""
import json
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.models.analysis import AnalysisRequest, AnalysisResult
from app.services.analysis_service import run_analysis, run_upload_analysis, get_analysis

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest):
    """Analyze a project from a local path or GitHub URL."""
    try:
        return run_analysis(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.post("/analyze/upload", response_model=AnalysisResult)
async def analyze_upload(
    folder_name: str = Form(...),
    paths: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """Analyze a project folder uploaded directly from the browser folder picker."""
    try:
        try:
            path_list = json.loads(paths)
        except Exception:
            raise ValueError("Invalid paths metadata in upload request.")

        if not files or not path_list:
            raise ValueError("No files provided for folder analysis.")

        return await run_upload_analysis(folder_name, path_list, files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis_by_id(analysis_id: str):
    result = get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result

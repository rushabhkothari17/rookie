"""Miscellaneous utility routes."""
from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/download/test-cases")
async def download_test_cases():
    """Download the comprehensive test cases CSV file."""
    file_path = "/app/test_cases_comprehensive.csv"
    
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Test cases file not found")
    
    return FileResponse(
        path=file_path,
        filename="test_cases_comprehensive.csv",
        media_type="text/csv"
    )

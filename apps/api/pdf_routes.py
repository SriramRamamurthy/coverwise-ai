from fastapi import APIRouter, File, HTTPException, UploadFile

from src.coverwise.clause_extraction import extract_clause_candidates
from src.coverwise.database import get_analysis, save_analysis
from src.coverwise.pdf_processing import (
    MAX_UPLOAD_BYTES,
    PDFProcessingError,
    extract_pdf_text,
)


router = APIRouter(prefix="/policies", tags=["Policy documents"])


@router.post("/extract")
def extract_policy(file: UploadFile = File(...)):
    filename = (file.filename or "uploaded.pdf").replace("\\", "/")
    filename = filename.rsplit("/", 1)[-1]

    try:
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Please upload a PDF file.",
            )

        content = file.file.read(MAX_UPLOAD_BYTES + 1)

        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Maximum PDF size is 10 MB.",
            )

        result = extract_pdf_text(content, filename)

    except PDFProcessingError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    finally:
        file.file.close()

    saved = save_analysis(
        inputs={
            "filename": filename,
            "document_hash": result["document_hash"],
        },
        result=result,
        analysis_type="pdf_extraction",
    )

    return {**result, **saved}


@router.post("/{analysis_id}/clauses")
def scan_policy_clauses(analysis_id: str):
    document = get_analysis(analysis_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document analysis not found.",
        )

    if document["analysis_type"] != "pdf_extraction":
        raise HTTPException(
            status_code=400,
            detail="Select a PDF extraction analysis.",
        )

    extraction = document["result"]
    candidates = extract_clause_candidates(extraction["pages"])

    result = {
        **candidates,
        "source_analysis_id": analysis_id,
        "filename": extraction["filename"],
        "document_hash": extraction["document_hash"],
        "extraction_status": extraction["extraction_status"],
        "extraction_warnings": extraction["warnings"],
    }

    saved = save_analysis(
        inputs={"source_analysis_id": analysis_id},
        result=result,
        analysis_type="clause_scan",
    )

    return {**result, **saved}
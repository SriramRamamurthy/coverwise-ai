from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.coverwise.database import get_analysis
from src.coverwise.reporting import build_report_content, render_pdf


router = APIRouter(prefix="/reports", tags=["Reports"])


def load_report(analysis_id):
    record = get_analysis(analysis_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found.",
        )

    if record["analysis_type"] not in {
        "reviewed_policy",
        "policy_comparison",
        "review_assessment",
    }:
        raise HTTPException(
            status_code=400,
            detail="Select a reviewed policy or policy comparison.",
        )

    return build_report_content(record)


@router.get("/{analysis_id}")
def report_preview(analysis_id: str):
    return load_report(analysis_id)


@router.get("/{analysis_id}/pdf")
def report_download(analysis_id: str):
    report = load_report(analysis_id)
    content = render_pdf(report)

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="CoverWise_{report["analysis_id"]}.pdf"'
            )
        },
    )
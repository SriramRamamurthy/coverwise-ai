import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.coverwise.database import get_analysis, save_analysis


router = APIRouter(prefix="/policies", tags=["Policy review"])


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


class ReviewedClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["unknown", "confirmed", "ambiguous"]
    value: str | None = Field(default=None, max_length=1000)
    source_page: int | None = Field(default=None, ge=1)
    evidence: str | None = Field(default=None, max_length=5000)
    conditions: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_review(self):
        if self.status == "confirmed":
            if (
                not self.value
                or not self.value.strip()
                or self.source_page is None
                or not self.evidence
                or not self.evidence.strip()
            ):
                raise ValueError(
                    "Confirmed findings require a value, "
                    "source page, and supporting quotation."
                )
        elif self.value is not None:
            raise ValueError(
                "Unknown or ambiguous findings cannot have "
                "a confirmed value."
            )

        if (self.source_page is None) != (self.evidence is None):
            raise ValueError(
                "Source page and evidence must be supplied together."
            )

        return self


class PolicyReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_plan: str = Field(min_length=1, max_length=200)
    age: int | None = Field(default=None, ge=1, le=120)
    family_details: str = Field(default="", max_length=1000)
    coverage_requirement: str = Field(default="", max_length=1000)
    annual_premium: float | None = Field(
        default=None, gt=0, allow_inf_nan=False
    )
    sum_insured: float | None = Field(
        default=None, gt=0, allow_inf_nan=False
    )

    copayment: ReviewedClause
    waiting_period: ReviewedClause
    room_rent: ReviewedClause
    reviewer_acknowledged: Literal[True]


@router.post("/{analysis_id}/review")
def save_policy_review(analysis_id: str, review: PolicyReview):
    document = get_analysis(analysis_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Source document not found.",
        )

    if document["analysis_type"] != "pdf_extraction":
        raise HTTPException(
            status_code=400,
            detail="The source must be a PDF extraction analysis.",
        )

    if not review.selected_plan.strip():
        raise HTTPException(
            status_code=422,
            detail="Enter the selected plan or variant.",
        )

    extraction = document["result"]
    page_text = {
        page["page_number"]: normalize_text(page["text"])
        for page in extraction["pages"]
    }

    clauses = {
        "copayment": review.copayment,
        "waiting_period": review.waiting_period,
        "room_rent": review.room_rent,
    }

    for name, clause in clauses.items():
        if clause.evidence is not None:
            quotation = normalize_text(clause.evidence)

            if (
                not quotation
                or clause.source_page not in page_text
                or quotation not in page_text[clause.source_page]
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{name}: quotation not found on the selected "
                        "page. Copy a continuous passage from the "
                        "extracted text."
                    ),
                )

    checklist = []

    for name, clause in clauses.items():
        if clause.status != "confirmed":
            checklist.append(
                {
                    "field": name,
                    "status": clause.status,
                    "message": (
                        "Interpretation remains unresolved. "
                        "Review the document or ask the insurer."
                    ),
                }
            )
        else:
            checklist.append(
                {
                    "field": name,
                    "status": "user_confirmed",
                    "message": (
                        "A user-reviewed finding has supporting text. "
                        "Its applicability still depends on stated "
                        "conditions and the selected plan."
                    ),
                }
            )

    result = {
        "source_analysis_id": analysis_id,
        "filename": extraction["filename"],
        "document_hash": extraction["document_hash"],
        "review": review.model_dump(),
        "checklist": checklist,
        "extraction_status": extraction["extraction_status"],
        "limitations": [
            "Values are user-confirmed interpretations, not automatic facts.",
            "Quotation matching checks text presence, not interpretation.",
            "This first review covers only three clause groups.",
            "No coverage score is calculated at this stage.",
            "Premium and sum insured are user-supplied values.",
        ],
    }

    saved = save_analysis(
        inputs={"source_analysis_id": analysis_id},
        result=result,
        analysis_type="reviewed_policy",
    )

    return {**result, **saved}
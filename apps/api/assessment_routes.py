from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from src.coverwise.database import get_analysis, save_analysis


router = APIRouter(prefix="/assessments", tags=["Reviewed assessment"])


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    copayment_percentage: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    ped_waiting_months: int | None = Field(
        default=None, ge=0, le=120
    )
    room_restriction_present: bool | None = None
    reviewer_acknowledged: Literal[True]


@router.post("")
def assess_review(request: AssessmentInput):
    record = get_analysis(request.review_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Review not found.",
        )

    if record["analysis_type"] != "reviewed_policy":
        raise HTTPException(
            status_code=400,
            detail="Select a saved policy review.",
        )

    reviewed_policy = record["result"]
    review = reviewed_policy["review"]

    supplied_signals = {
        "copayment": request.copayment_percentage,
        "waiting_period": request.ped_waiting_months,
        "room_rent": request.room_restriction_present,
    }

    for field, value in supplied_signals.items():
        if value is not None and review[field]["status"] != "confirmed":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{field}: confirm the source finding in the "
                    "policy review before supplying a structured value."
                ),
            )

    clause_fields = ["copayment", "waiting_period", "room_rent"]

    confirmed_count = sum(
        review[field]["status"] == "confirmed"
        for field in clause_fields
    )

    completeness_score = round(confirmed_count / 3 * 100)

    unresolved = [
        f"{field}: {review[field]['status']}"
        for field in clause_fields
        if review[field]["status"] != "confirmed"
    ]

    flags = []

    if request.copayment_percentage is None:
        unresolved.append("Co-payment percentage was not supplied.")
    elif request.copayment_percentage > 0:
        flags.append(
            f"Reviewed co-payment: {request.copayment_percentage:g}%. "
            "Check its triggers, exceptions, and eligible claim basis."
        )

    if request.ped_waiting_months is None:
        unresolved.append(
            "Pre-existing disease waiting period was not supplied."
        )
    elif request.ped_waiting_months > 0:
        flags.append(
            f"Reviewed PED waiting period: "
            f"{request.ped_waiting_months} months. "
            "Verify applicability and continuity credits."
        )

    if request.room_restriction_present is None:
        unresolved.append("Room-restriction presence was not supplied.")
    elif request.room_restriction_present:
        flags.append(
            "A room-rent or room-category restriction was confirmed. "
            "Check its limit, unit, and deduction conditions."
        )

    if reviewed_policy["extraction_status"] == "partial":
        unresolved.append(
            "Some PDF pages were unreadable."
        )

    if unresolved:
        review_status = "Further review needed"
    elif flags:
        review_status = "Reviewed; restrictions identified"
    else:
        review_status = "Reviewed within the three-clause scope"

    assessment = {
        "review_completeness_score": completeness_score,
        "confirmed_clause_groups": confirmed_count,
        "total_clause_groups": 3,
        "review_status": review_status,
        "restriction_flags": flags,
        "unresolved_items": unresolved,
        "structured_inputs": {
            "copayment_percentage": request.copayment_percentage,
            "ped_waiting_months": request.ped_waiting_months,
            "room_restriction_present": request.room_restriction_present,
        },
        "method": "three_clause_review_completeness_v1",
        "limitations": [
            "The score measures review completion, not coverage strength.",
            "Structured values are user-confirmed interpretations.",
            "Zero flags does not establish unrestricted coverage.",
            "This is not a claim-rejection probability or insurance risk rating.",
            "Only three clause groups are assessed.",
        ],
    }

    result = {
        "source_review_id": request.review_id,
        "reviewed_policy": reviewed_policy,
        "assessment": assessment,
    }

    saved = save_analysis(
        inputs=request.model_dump(),
        result=result,
        analysis_type="review_assessment",
    )

    return {**result, **saved}
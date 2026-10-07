from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from src.coverwise.database import get_analysis, save_analysis


router = APIRouter(prefix="/comparisons", tags=["Policy comparison"])


class ComparisonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_review_id: str
    proposed_review_id: str
    amounts_comparable: bool = False


def load_review(analysis_id):
    record = get_analysis(analysis_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Review not found: {analysis_id}",
        )

    if record["analysis_type"] != "reviewed_policy":
        raise HTTPException(
            status_code=400,
            detail="Both selections must be saved policy reviews.",
        )

    return record["result"]


@router.post("")
def compare_policies(request: ComparisonInput):
    if request.current_review_id == request.proposed_review_id:
        raise HTTPException(
            status_code=400,
            detail="Select two different saved reviews.",
        )

    current = load_review(request.current_review_id)
    proposed = load_review(request.proposed_review_id)

    current_values = current["review"]
    proposed_values = proposed["review"]

    rows = []
    advisor_questions = []

    fields = [
        ("copayment", "Co-payment"),
        ("waiting_period", "Waiting periods"),
        ("room_rent", "Room-rent restrictions"),
    ]

    for key, label in fields:
        left = current_values[key]
        right = proposed_values[key]

        both_confirmed = (
            left["status"] == "confirmed"
            and right["status"] == "confirmed"
        )

        if not both_confirmed:
            comparison_status = "Unresolved"
            explanation = (
                "At least one finding is unknown or ambiguous."
            )
            advisor_questions.append(
                f"Confirm {label.lower()} for both selected plans "
                "and explain the applicable conditions."
            )
        else:
            same_value = (
                " ".join(left["value"].split()).casefold()
                == " ".join(right["value"].split()).casefold()
            )
            same_conditions = (
                " ".join(left["conditions"].split()).casefold()
                == " ".join(right["conditions"].split()).casefold()
            )

            if same_value and same_conditions:
                comparison_status = "Same reviewed wording"
                explanation = (
                    "The recorded interpretations match. "
                    "This does not establish contractual equivalence."
                )
            else:
                comparison_status = "Difference needs review"
                explanation = (
                    "Recorded values or conditions differ. "
                    "Check applicability before interpreting the change."
                )
                advisor_questions.append(
                    f"Explain how the difference in {label.lower()} "
                    "affects the selected plans and user scenario."
                )

        rows.append(
            {
                "clause": label,
                "current_value": left["value"] or "Not confirmed",
                "proposed_value": right["value"] or "Not confirmed",
                "current_status": left["status"],
                "proposed_status": right["status"],
                "current_conditions": left["conditions"],
                "proposed_conditions": right["conditions"],
                "comparison_status": comparison_status,
                "explanation": explanation,
                "current_page": left["source_page"],
                "proposed_page": right["source_page"],
                "current_evidence": left["evidence"],
                "proposed_evidence": right["evidence"],
            }
        )

    amount_comparison = []

    for key, label in [
        ("annual_premium", "Annual premium"),
        ("sum_insured", "Sum insured"),
    ]:
        left = current_values[key]
        right = proposed_values[key]

        if request.amounts_comparable and left is not None and right is not None:
            amount_comparison.append(
                {
                    "field": label,
                    "current": left,
                    "proposed": right,
                    "change": right - left,
                    "change_percentage": round(
                        (right - left) / left * 100, 2
                    ),
                }
            )

    warnings = [
        "This comparison covers three reviewed clause groups only.",
        "Differences are not automatic improvements or downgrades.",
        "Amounts are user-supplied and do not establish fair pricing.",
        "Switching and continuity benefits require insurer confirmation.",
    ]

    if (
        current["extraction_status"] == "partial"
        or proposed["extraction_status"] == "partial"
    ):
        warnings.append(
            "At least one document has unreadable pages."
        )

    for key in ["age", "family_details", "coverage_requirement"]:
        if current_values[key] != proposed_values[key]:
            warnings.append(
                f"User context differs for {key}. "
                "Check that both reviews describe the same scenario."
            )

    advisor_questions.append(
        "Before switching, confirm continuity credits, remaining "
        "waiting periods, and whether additional coverage has new conditions."
    )

    result = {
        "current_review_id": request.current_review_id,
        "proposed_review_id": request.proposed_review_id,
        "current_document": current["filename"],
        "proposed_document": proposed["filename"],
        "current_plan": current_values["selected_plan"],
        "proposed_plan": proposed_values["selected_plan"],
        "clause_comparison": rows,
        "amount_comparison": amount_comparison,
        "advisor_questions": advisor_questions,
        "warnings": warnings,
    }

    saved = save_analysis(
        inputs=request.model_dump(),
        result=result,
        analysis_type="policy_comparison",
    )

    return {**result, **saved}
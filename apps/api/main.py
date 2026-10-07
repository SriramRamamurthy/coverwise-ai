from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.coverwise.database import (
    get_analysis,
    initialize_database,
    list_analyses,
    save_analysis,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = (
    PROJECT_ROOT / "models" / "coverage_decision_tree.joblib"
)


@asynccontextmanager
async def lifespan(app):
    initialize_database()
    yield


app = FastAPI(
    title="CoverWise API",
    version="0.3.0",
    lifespan=lifespan,
)


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    policy_type: Literal[
        "Individual Health",
        "Family Floater",
        "Senior Citizen",
        "Group Health",
        "Critical Illness",
        "Top-up Health",
    ]

    sum_insured: float = Field(gt=0)
    annual_premium: float = Field(gt=0)
    waiting_period_months: int = Field(ge=0, le=48)
    pre_existing_disease_waiting_period_months: int = Field(
        ge=0, le=48
    )
    copayment_percentage: float = Field(ge=0, le=30)
    room_rent_limit_present: Literal[0, 1]
    icu_limit_present: Literal[0, 1]
    disease_sub_limit_count: int = Field(ge=0, le=6)
    exclusion_count: int = Field(ge=3, le=22)
    restoration_benefit_present: Literal[0, 1]
    no_claim_bonus_present: Literal[0, 1]
    child_coverage_present: Literal[0, 1]
    maternity_coverage_present: Literal[0, 1]


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "application": "CoverWise",
        "model_available": MODEL_PATH.exists(),
    }


@app.post("/predict")
def predict_coverage(policy: PolicyInput):
    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Model missing. Run ml/train_model.py first.",
        )

    bundle = joblib.load(MODEL_PATH)
    pipeline = bundle["pipeline"]

    features = policy.model_dump()
    features["premium_to_coverage_ratio"] = round(
        policy.annual_premium / policy.sum_insured,
        4,
    )

    inputs = pd.DataFrame([features])[bundle["features"]]
    predicted_label = str(pipeline.predict(inputs)[0])
    probabilities = pipeline.predict_proba(inputs)[0]
    classes = pipeline.named_steps["classifier"].classes_

    warnings = [
        "Experimental model: test accuracy 51%; macro-F1 0.43.",
        "High Risk recall was 1 of 7 test cases.",
        "Synthetic training labels are not validated insurance judgments.",
        "Class probabilities are not calibrated confidence scores.",
    ]

    ratio = features["premium_to_coverage_ratio"]
    if (
        not 300000 <= policy.sum_insured <= 5000000
        or not 1800 <= policy.annual_premium <= 288400
        or not 0.006 <= ratio <= 0.062
    ):
        warnings.append(
            "Some monetary inputs are outside observed training ranges."
        )

    result = {
        "predicted_label": predicted_label,
        "model_version": bundle["model_version"],
        "assessment_type": "experimental_ml",
        "class_probabilities": {
            str(label): float(probability)
            for label, probability in zip(classes, probabilities)
        },
        "features_used": features,
        "warnings": warnings,
    }

    saved = save_analysis(
        inputs=features,
        result=result,
        analysis_type="experimental_ml",
    )

    return {**result, **saved}


@app.get("/analyses")
def analysis_history(limit: int = Query(default=20, ge=1, le=100)):
    return {"analyses": list_analyses(limit)}


@app.get("/analyses/{analysis_id}")
def analysis_detail(analysis_id: str):
    analysis = get_analysis(analysis_id)

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found.",
        )

    return analysis
from apps.api.pdf_routes import router as pdf_router

app.include_router(pdf_router)

from apps.api.review_routes import router as review_router

app.include_router(review_router)

from apps.api.comparison_routes import router as comparison_router

app.include_router(comparison_router)

from apps.api.question_routes import router as question_router

app.include_router(question_router)

from apps.api.report_routes import router as report_router

app.include_router(report_router)

from apps.api.assessment_routes import router as assessment_router

app.include_router(assessment_router)
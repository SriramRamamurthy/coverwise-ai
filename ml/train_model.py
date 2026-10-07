import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, export_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "coverwise_synthetic_coverage_risk_dataset_500.csv"
)

MODEL_DIR = PROJECT_ROOT / "models"
REPORT_DIR = PROJECT_ROOT / "reports"

FEATURES = [
    "policy_type",
    "sum_insured",
    "annual_premium",
    "premium_to_coverage_ratio",
    "waiting_period_months",
    "pre_existing_disease_waiting_period_months",
    "copayment_percentage",
    "room_rent_limit_present",
    "icu_limit_present",
    "disease_sub_limit_count",
    "exclusion_count",
    "restoration_benefit_present",
    "no_claim_bonus_present",
    "child_coverage_present",
    "maternity_coverage_present",
]

TARGET = "risk_label"
LABELS = [
    "Strong Coverage",
    "Moderate Coverage",
    "Caution Required",
    "High Risk",
]


def evaluate(y_true, y_pred):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(
            f1_score(
                y_true,
                y_pred,
                labels=LABELS,
                average="macro",
                zero_division=0,
            )
        ),
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=LABELS,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            y_true,
            y_pred,
            labels=LABELS,
        ).tolist(),
    }


def main():
    df = pd.read_csv(DATASET_PATH)

    required = FEATURES + [TARGET, "policy_id"]
    missing_columns = set(required) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns: {sorted(missing_columns)}"
        )

    if df[required].isna().any().any():
        raise ValueError(
            "Missing values found. Review them before training."
        )

    unknown_labels = set(df[TARGET]) - set(LABELS)
    if unknown_labels:
        raise ValueError(
            f"Unexpected target labels: {sorted(unknown_labels)}"
        )

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    categorical_features = ["policy_type"]
    numeric_features = [
        name for name in FEATURES
        if name not in categorical_features
    ]

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "policy_type",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features,
            ),
            (
                "numeric",
                "passthrough",
                numeric_features,
            ),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            (
                "classifier",
                DecisionTreeClassifier(
                    max_depth=4,
                    min_samples_leaf=5,
                    random_state=42,
                ),
            ),
        ]
    )

    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)

    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train, y_train)
    baseline_predictions = baseline.predict(X_test)

    tree_metrics = evaluate(y_test, predictions)
    baseline_metrics = evaluate(y_test, baseline_predictions)

    print("\nDATA SPLIT")
    print(f"Training records: {len(X_train)}")
    print(f"Testing records: {len(X_test)}")

    print("\nTEST CLASS COUNTS")
    print(y_test.value_counts().to_string())

    print("\nMODEL COMPARISON")
    comparison = pd.DataFrame(
        {
            "Most-frequent baseline": {
                "accuracy": baseline_metrics["accuracy"],
                "macro_f1": baseline_metrics["macro_f1"],
            },
            "Decision Tree": {
                "accuracy": tree_metrics["accuracy"],
                "macro_f1": tree_metrics["macro_f1"],
            },
        }
    ).T
    print(comparison.round(4).to_string())

    print("\nDECISION TREE CLASSIFICATION REPORT")
    print(
        classification_report(
            y_test,
            predictions,
            labels=LABELS,
            zero_division=0,
        )
    )

    print("\nCONFUSION MATRIX")
    print("Rows = actual labels; columns = predicted labels")
    matrix = pd.DataFrame(
        tree_metrics["confusion_matrix"],
        index=LABELS,
        columns=LABELS,
    )
    print(matrix.to_string())

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    model_bundle = {
        "pipeline": pipeline,
        "features": FEATURES,
        "labels": LABELS,
        "model_version": "0.1.0",
        "training_source": DATASET_PATH.name,
        "limitation": (
            "Trained on synthetic labels; "
            "not validated as real-world insurance risk."
        ),
    }

    joblib.dump(
        model_bundle,
        MODEL_DIR / "coverage_decision_tree.joblib",
    )

    evaluation = {
        "random_seed": 42,
        "training_records": len(X_train),
        "testing_records": len(X_test),
        "features": FEATURES,
        "label_order": LABELS,
        "test_policy_ids": df.loc[
            X_test.index, "policy_id"
        ].tolist(),
        "baseline": baseline_metrics,
        "decision_tree": tree_metrics,
    }

    (REPORT_DIR / "coverage_model_metrics.json").write_text(
        json.dumps(evaluation, indent=2),
        encoding="utf-8",
    )

    encoded_feature_names = (
        pipeline.named_steps["preprocessing"]
        .get_feature_names_out()
        .tolist()
    )

    tree_description = export_text(
        pipeline.named_steps["classifier"],
        feature_names=encoded_feature_names,
    )

    (REPORT_DIR / "coverage_tree_rules.txt").write_text(
        tree_description,
        encoding="utf-8",
    )

    print("\nSAVED")
    print("models/coverage_decision_tree.joblib")
    print("reports/coverage_model_metrics.json")
    print("reports/coverage_tree_rules.txt")


if __name__ == "__main__":
    main()
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "coverwise_synthetic_coverage_risk_dataset_500.csv"
)


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    df = pd.read_csv(DATASET_PATH)

    required_columns = {"policy_id", "risk_label", "coverage_clarity_score"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Required columns missing: {sorted(missing_columns)}"
        )

    print("\nDATASET SIZE")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\nCOLUMN TYPES")
    print(df.dtypes.to_string())

    print("\nMISSING VALUES")
    missing = df.isna().sum()
    print(
        missing[missing > 0].to_string()
        if missing.any()
        else "No missing values found."
    )

    text_columns = df.select_dtypes(include=["object", "string"])
    blank_counts = text_columns.apply(
        lambda column: column.astype("string")
        .str.strip()
        .eq("")
        .sum()
    )

    print("\nBLANK TEXT VALUES")
    print(
        blank_counts[blank_counts > 0].to_string()
        if blank_counts.any()
        else "No blank text values found."
    )

    print("\nDUPLICATES")
    print(f"Duplicate complete rows: {df.duplicated().sum()}")

    without_id = df.drop(columns=["policy_id"])
    print(
        "Duplicate rows excluding policy_id: "
        f"{without_id.duplicated().sum()}"
    )
    print(f"Repeated policy IDs: {df['policy_id'].duplicated().sum()}")

    print("\nTARGET DISTRIBUTION")
    counts = df["risk_label"].value_counts(dropna=False)

    distribution = pd.DataFrame({
        "count": counts,
        "percentage": (counts / len(df) * 100).round(2),
    })
    print(distribution.to_string())

    print("\nNUMERIC FEATURE RANGES")
    numeric = df.select_dtypes(include="number")
    print(numeric.agg(["min", "max"]).T.to_string())

    print("\nSUPPLIED SCORE BY TARGET LABEL")
    score_summary = df.groupby("risk_label")[
        "coverage_clarity_score"
    ].agg(["count", "min", "max", "mean"])

    print(score_summary.round(2).to_string())

    print("\nPOLICY TYPES")
    if "policy_type" in df.columns:
        print(df["policy_type"].value_counts(dropna=False).to_string())

    print("\nInspection complete. No data was modified.")


if __name__ == "__main__":
    main()
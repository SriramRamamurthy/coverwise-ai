# CoverWise AI

A local insurance-policy review prototype built with Streamlit,
FastAPI, SQLite, and scikit-learn. No LLM or external AI API is used.

## Features

- Text-readable PDF extraction with physical page references.
- Candidate evidence for co-payment, waiting periods, and room rent.
- User-reviewed findings with supporting-quotation validation.
- Comparison of saved policy reviews.
- TF-IDF search for relevant policy passages.
- Review-completeness assessment and restriction flags.
- PDF summaries and reports.
- SQLite analysis history.
- Experimental Decision Tree coverage classifier.

## Setup

Developed using Python 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ml/inspect_dataset.py
python ml/train_model.py
```

Start the backend from the repository root:

```bash
python -m uvicorn apps.api.main:app --reload --port 8000
```

In another terminal, activate the environment and start the UI:

```bash
source .venv/bin/activate
python -m streamlit run apps/ui/app.py
```

UI: http://localhost:8501
API documentation: http://127.0.0.1:8000/docs

## Usage

1. Upload a public or anonymized text-readable policy PDF.
2. Inspect the extracted text and candidate clause evidence.
3. Review applicable terms for the selected plan and save findings.
4. Use the comparison, questions, assessment, and reports pages.
5. For ML demonstration, use the separate experimental input form.

SQLite history is created locally in `storage/coverwise.db`.
The trained model is created in `models/`.
Neither is included in the repository.

## Model evaluation

The initial Decision Tree used 400 training and 100 test records
from the supplied synthetic coverage dataset.

- Accuracy: 51%.
- Macro-F1: approximately 0.43.
- High Risk recall: 1 of 7 test cases.
- Most-frequent baseline accuracy: 36%.

This model is experimental and not validated for real insurance decisions.

## Important limitations

- Clause extraction/review currently covers three clause groups.
- Scanned PDFs without readable text are unsupported; OCR is pending.
- Search retrieves candidate passages, not generated answers.
- Comparison flags reviewed differences without automatically declaring
  improvements or downgrades.
- The completeness score measures review completion, not coverage quality.
- PDF export uses escape notation for non-ASCII characters.
- Synthetic labels do not establish real-world insurance risk.
- Broader clause coverage, semantic search, ACKO regression, and deployment
  remain pending.
- This prototype substitutes rules, templates, and passage retrieval for
  the brief's LLM-based features.
- End-to-end evaluation is still pending.

## Data

The supplied CoverWise synthetic dataset is included for reproducibility.
Its provenance and usage notes are documented in the project resources.
The application requires users to provide their own public or anonymized
sample policy PDFs.

Do not commit private policies, personal data, or local analysis history.

## Disclaimer

For policy understanding and educational demonstration only.
Verify interpretations with the insurer or a licensed advisor.
This application does not provide final financial, legal, medical,
or insurance advice.
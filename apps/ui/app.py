import os

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "COVERWISE_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="CoverWise",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ CoverWise")
st.caption("Policy understanding and coverage restriction review")

st.info(
    "Decision-support prototype. Verify policy findings with your "
    "insurer or advisor before making decisions."
)

with st.sidebar:
    st.header("Backend")
    if st.button("Check connection"):
        try:
            response = requests.get(
                f"{API_BASE_URL}/health",
                timeout=10,
            )
            response.raise_for_status()
            st.json(response.json())
        except (requests.RequestException, ValueError) as error:
            st.error(f"Connection check failed: {error}")

st.subheader("Experimental coverage classifier")

st.warning(
    "This model achieved 51% test accuracy and identified only "
    "1 of 7 High Risk test cases. Its prediction is experimental."
)

st.caption(
    "The initial values are a synthetic example, not extracted "
    "policy facts. Replace them with reviewed inputs when available."
)

with st.form("policy_input_form"):
    policy_type = st.selectbox(
        "Policy type",
        [
            "Senior Citizen",
            "Individual Health",
            "Family Floater",
            "Group Health",
            "Critical Illness",
            "Top-up Health",
        ],
    )

    payload = {"policy_type": policy_type}

    # Label, API field name, minimum, maximum, example value.
    numeric_fields = [
        ("Sum insured", "sum_insured", 1, None, 300000),
        ("Annual premium", "annual_premium", 1, None, 14900),
        ("General waiting period (months)",
         "waiting_period_months", 0, 48, 3),
        ("Pre-existing disease waiting period (months)",
         "pre_existing_disease_waiting_period_months", 0, 48, 12),
        ("Co-payment (%)", "copayment_percentage", 0, 30, 0),
        ("Disease sub-limit count",
         "disease_sub_limit_count", 0, 6, 2),
        ("Exclusion count", "exclusion_count", 3, 22, 21),
    ]

    left, right = st.columns(2)

    for index, (label, field, minimum, maximum, value) in enumerate(
        numeric_fields
    ):
        with (left if index % 2 == 0 else right):
            payload[field] = st.number_input(
                label,
                min_value=minimum,
                max_value=maximum,
                value=value,
                step=1,
                key=field,
            )

    st.caption(
        "Sum insured and premium must use the same currency. "
        "Confirm the source dataset's units before real-world use."
    )

    binary_fields = [
        ("Room-rent limit present", "room_rent_limit_present", 1),
        ("ICU limit present", "icu_limit_present", 0),
        ("Restoration benefit present", "restoration_benefit_present", 1),
        ("No-claim bonus present", "no_claim_bonus_present", 1),
        ("Child coverage present", "child_coverage_present", 1),
        ("Maternity coverage present", "maternity_coverage_present", 0),
    ]

    for index, (label, field, example_value) in enumerate(binary_fields):
        with (left if index % 2 == 0 else right):
            selection = st.selectbox(
                label,
                ["No", "Yes"],
                index=example_value,
                key=field,
            )
            payload[field] = int(selection == "Yes")

    reviewed = st.checkbox(
        "I am testing the labeled synthetic example, or have "
        "reviewed every input. Unknown values are not being "
        "treated as No or zero."
    )

    submitted = st.form_submit_button(
        "Run experimental prediction",
        type="primary",
    )

if submitted:
    st.session_state.pop("prediction_result", None)

    if not reviewed:
        st.error("Review the inputs and acknowledge their source first.")
    else:
        try:
            with st.spinner("Running prediction..."):
                response = requests.post(
                    f"{API_BASE_URL}/predict",
                    json=payload,
                    timeout=30,
                )

            if response.ok:
                st.session_state["prediction_result"] = response.json()
            else:
                st.error(
                    f"Backend rejected the request "
                    f"(HTTP {response.status_code})."
                )
                st.code(response.text)

        except (requests.RequestException, ValueError) as error:
            st.error(f"Prediction failed: {error}")

result = st.session_state.get("prediction_result")

if result:
    st.subheader("Experimental result")
    st.metric("Predicted category", result["predicted_label"])

    probabilities = pd.DataFrame(
        [
            {"Category": label, "Probability": probability}
            for label, probability in
            result["class_probabilities"].items()
        ]
    )
    st.dataframe(probabilities, hide_index=True)

    st.caption(
        "Probabilities describe the fitted model's class distribution; "
        "they are not claim-rejection probabilities or a clarity score."
    )

    with st.expander("Inputs used"):
        st.json(result["features_used"])

    with st.expander("Model limitations", expanded=True):
        for warning in result["warnings"]:
            st.write(f"• {warning}")

st.divider()
st.subheader("Saved analysis history")

if st.button("Refresh history"):
    try:
        response = requests.get(
            f"{API_BASE_URL}/analyses",
            timeout=10,
        )
        response.raise_for_status()

        st.session_state["analysis_history"] = (
            response.json()["analyses"]
        )

    except (requests.RequestException, ValueError, KeyError) as error:
        st.session_state.pop("analysis_history", None)
        st.error(f"Could not load history: {error}")

history = st.session_state.get("analysis_history")

if history is not None:
    if not history:
        st.info("No saved analyses yet. Run a prediction first.")
    else:
        st.dataframe(pd.DataFrame(history), hide_index=True)

        summaries = {
            item["analysis_id"]: (
                f"{item['created_at']} — "
                f"{item['predicted_label'] or item['analysis_type']} — "
                f"{item['analysis_id'][:8]}"
            )
            for item in history
        }

        selected_id = st.selectbox(
            "Choose a saved analysis",
            options=list(summaries),
            format_func=lambda value: summaries[value],
        )

        if st.button("Open saved analysis"):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/analyses/{selected_id}",
                    timeout=10,
                )
                response.raise_for_status()
                st.json(response.json())

            except (requests.RequestException, ValueError) as error:
                st.error(f"Could not open analysis: {error}")
st.divider()
st.subheader("Policy PDF text extraction")

st.caption(
    "Upload a public or anonymized text-readable PDF, up to 10 MB "
    "and 100 pages. Extracted text is saved in your local SQLite database."
)

uploaded_pdf = st.file_uploader(
    "Choose a policy document",
    type=["pdf"],
    key="policy_pdf_upload",
)

if st.button("Extract PDF text", type="primary"):
    st.session_state.pop("pdf_result", None)

    if uploaded_pdf is None:
        st.error("Choose a PDF first.")
    elif uploaded_pdf.size > 10 * 1024 * 1024:
        st.error("Maximum PDF size is 10 MB.")
    else:
        try:
            with st.spinner("Extracting PDF text..."):
                response = requests.post(
                    f"{API_BASE_URL}/policies/extract",
                    files={
                        "file": (
                            uploaded_pdf.name,
                            uploaded_pdf.getvalue(),
                            "application/pdf",
                        )
                    },
                    timeout=120,
                )

            if response.ok:
                st.session_state["pdf_result"] = response.json()
            else:
                try:
                    detail = response.json().get(
                        "detail", response.text
                    )
                except ValueError:
                    detail = response.text

                st.error(f"Extraction failed: {detail}")

        except (requests.RequestException, ValueError) as error:
            st.error(f"Extraction request failed: {error}")

pdf_result = st.session_state.get("pdf_result")

if pdf_result:
    st.write(f"**Processed file:** {pdf_result['filename']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total pages", pdf_result["page_count"])
    col2.metric("Readable pages", pdf_result["readable_pages"])
    col3.metric("Extraction status", pdf_result["extraction_status"])

    st.caption(pdf_result["page_numbering"])

    for warning in pdf_result["warnings"]:
        st.warning(warning)

    for page in pdf_result["pages"]:
        with st.expander(
            f"Page {page['page_number']} — {page['status']}"
        ):
            if page["text"]:
                st.text(page["text"])
            else:
                st.write("No readable text available.")

    st.caption(
        f"Saved analysis ID: {pdf_result['analysis_id']}. "
        "Text extraction alone does not establish policy coverage."
    )
st.divider()
st.subheader("Clause evidence and uncertainty")

if pdf_result:
    st.caption(
        f"Scan source: {pdf_result['filename']}. "
        "Detected passages require human review."
    )

    if st.button("Find clause evidence"):
        st.session_state.pop("clause_result", None)

        try:
            with st.spinner("Searching for clause passages..."):
                response = requests.post(
                    f"{API_BASE_URL}/policies/"
                    f"{pdf_result['analysis_id']}/clauses",
                    timeout=30,
                )

            if response.ok:
                st.session_state["clause_result"] = response.json()
            else:
                st.error(
                    f"Clause scan failed "
                    f"(HTTP {response.status_code})."
                )
                st.code(response.text)

        except (requests.RequestException, ValueError) as error:
            st.error(f"Clause scan request failed: {error}")

    clause_result = st.session_state.get("clause_result")

    # Only display findings belonging to the current processed PDF.
    if (
        clause_result
        and clause_result["source_analysis_id"]
        == pdf_result["analysis_id"]
    ):
        if clause_result["extraction_status"] == "partial":
            st.warning(
                "Some pages were not readable. "
                "This clause search covers only extracted text."
            )

        summary = [
            {
                "Clause": finding["label"],
                "Status": finding["status"],
                "Keyword matches": finding["keyword_matches"],
                "Confirmed value": "Not confirmed",
            }
            for finding in clause_result["findings"]
        ]

        st.dataframe(pd.DataFrame(summary), hide_index=True)

        for finding in clause_result["findings"]:
            with st.expander(
                f"{finding['label']} — {finding['status']}",
                expanded=True,
            ):
                st.write(finding["review_question"])

                if not finding["evidence"]:
                    st.info(
                        "No supported keyword match found. "
                        "Review the original document."
                    )

                for evidence in finding["evidence"]:
                    st.markdown(
                        f"**Physical PDF page "
                        f"{evidence['page_number']}**"
                    )
                    st.text(evidence["excerpt"])

                if finding["evidence_display_limited"]:
                    st.caption(
                        "Additional matches exist. "
                        "Only the first six excerpts are displayed."
                    )

        with st.expander("Extraction limitations"):
            for limitation in clause_result["limitations"]:
                st.write(f"• {limitation}")

else:
    st.info("Extract a policy PDF first to search for clause evidence.")

st.divider()
st.subheader("Review policy findings")

if pdf_result:
    document_id = pdf_result["analysis_id"]

    st.caption(
        "Confirm terms for the selected plan. "
        "Copy supporting quotations from the extracted page text. "
        "Leave unresolved findings unknown or ambiguous."
    )

    with st.form(f"review_form_{document_id}"):
        selected_plan = st.text_input(
            "Selected plan or variant",
            placeholder="For example: Gold",
        )

        age = st.number_input(
            "Age — use 0 if not supplied",
            min_value=0,
            max_value=120,
            value=0,
        )

        family_details = st.text_input(
            "Family details — optional",
            placeholder="For example: two adults and one child",
        )

        coverage_requirement = st.text_area(
            "Coverage requirement or concern — optional",
            placeholder="For example: understand child eligibility",
        )

        col1, col2 = st.columns(2)

        with col1:
            annual_premium = st.number_input(
                "Annual premium — 0 means not supplied",
                min_value=0.0,
                value=0.0,
                step=100.0,
            )

        with col2:
            sum_insured = st.number_input(
                "Sum insured — 0 means not supplied",
                min_value=0.0,
                value=0.0,
                step=10000.0,
            )

        st.caption(
            "Use the same currency for both amounts. "
            "These are user-supplied values."
        )

        reviewed_clauses = {}

        review_fields = [
            (
                "copayment",
                "Co-payment",
                "Example interpretation: Not applicable to selected plan",
            ),
            (
                "waiting_period",
                "Waiting periods",
                "Record the type, duration, and applicable plan",
            ),
            (
                "room_rent",
                "Room-rent restrictions",
                "Record the cap, unit, room category, and conditions",
            ),
        ]

        for field, label, guidance in review_fields:
            st.markdown(f"**{label}**")
            st.caption(guidance)

            status = st.selectbox(
                "Review status",
                ["unknown", "confirmed", "ambiguous"],
                key=f"{document_id}_{field}_status",
            )

            value = st.text_input(
                "Reviewed interpretation — used only when confirmed",
                key=f"{document_id}_{field}_value",
            )

            source_page = st.number_input(
                "Physical PDF page containing the quotation",
                min_value=1,
                max_value=pdf_result["page_count"],
                value=1,
                key=f"{document_id}_{field}_page",
            )

            evidence = st.text_area(
                "Supporting quotation — copy a continuous passage",
                key=f"{document_id}_{field}_evidence",
            )

            conditions = st.text_area(
                "Conditions, exceptions, or unresolved questions",
                key=f"{document_id}_{field}_conditions",
            )

            reviewed_clauses[field] = {
                "status": status,
                "value": (
                    value.strip()
                    if status == "confirmed"
                    else None
                ),
                "source_page": (
                    source_page if evidence.strip() else None
                ),
                "evidence": evidence.strip() or None,
                "conditions": conditions.strip(),
            }

        acknowledged = st.checkbox(
            "I reviewed the selected plan and supporting passages. "
            "Unknown terms have not been converted to No or zero."
        )

        save_review = st.form_submit_button(
            "Save reviewed findings",
            type="primary",
        )

    if save_review:
        st.session_state.pop("policy_review_result", None)

        if not acknowledged:
            st.error("Review the findings and acknowledge them first.")
        elif not selected_plan.strip():
            st.error("Enter the selected plan or variant.")
        else:
            payload = {
                "selected_plan": selected_plan.strip(),
                "age": age or None,
                "family_details": family_details.strip(),
                "coverage_requirement": coverage_requirement.strip(),
                "annual_premium": annual_premium or None,
                "sum_insured": sum_insured or None,
                **reviewed_clauses,
                "reviewer_acknowledged": True,
            }

            try:
                response = requests.post(
                    f"{API_BASE_URL}/policies/{document_id}/review",
                    json=payload,
                    timeout=30,
                )

                if response.ok:
                    st.session_state["policy_review_result"] = (
                        response.json()
                    )
                else:
                    st.error("Review could not be saved.")
                    st.code(response.text)

            except (requests.RequestException, ValueError) as error:
                st.error(f"Review request failed: {error}")

    saved_review = st.session_state.get("policy_review_result")

    if (
        saved_review
        and saved_review["source_analysis_id"] == document_id
    ):
        st.success("Reviewed findings saved.")
        st.write(
            f"**Selected plan:** "
            f"{saved_review['review']['selected_plan']}"
        )
        st.dataframe(
            pd.DataFrame(saved_review["checklist"]),
            hide_index=True,
        )

        with st.expander("Saved review and source references"):
            st.json(saved_review)

else:
    st.info("Extract a PDF before reviewing policy findings.")
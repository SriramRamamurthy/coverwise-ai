import os

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "COVERWISE_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="Policy Comparison",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Policy Comparison")
st.caption("Compare two saved, user-reviewed policy records.")

if st.button("Load saved policy reviews"):
    st.session_state.pop("comparison_result", None)

    try:
        response = requests.get(
            f"{API_BASE_URL}/analyses",
            params={"limit": 100},
            timeout=10,
        )
        response.raise_for_status()

        st.session_state["comparison_reviews"] = [
            item
            for item in response.json()["analyses"]
            if item["analysis_type"] == "reviewed_policy"
        ]

    except (requests.RequestException, ValueError, KeyError) as error:
        st.session_state.pop("comparison_reviews", None)
        st.error(f"Could not load reviews: {error}")

reviews = st.session_state.get("comparison_reviews", [])

if len(reviews) < 2:
    st.info(
        "Save at least two policy reviews on the main page, "
        "then load them here. Two reviewed variants of the same "
        "document can also be compared."
    )
else:
    labels = {
        item["analysis_id"]: (
            f"{item['created_at']} — "
            f"{item['analysis_id'][:8]}"
        )
        for item in reviews
    }

    st.dataframe(pd.DataFrame(reviews), hide_index=True)

    with st.form("comparison_form"):
        current_id = st.selectbox(
            "Current policy review",
            list(labels),
            format_func=lambda value: labels[value],
        )

        proposed_id = st.selectbox(
            "Proposed policy review",
            list(labels),
            index=1,
            format_func=lambda value: labels[value],
        )

        comparable = st.checkbox(
            "The entered amounts use the same currency, annual "
            "premium basis, and comparable coverage arrangement."
        )

        submitted = st.form_submit_button(
            "Compare policies",
            type="primary",
        )

    if submitted:
        st.session_state.pop("comparison_result", None)

        if current_id == proposed_id:
            st.error("Select two different reviews.")
        else:
            try:
                response = requests.post(
                    f"{API_BASE_URL}/comparisons",
                    json={
                        "current_review_id": current_id,
                        "proposed_review_id": proposed_id,
                        "amounts_comparable": comparable,
                    },
                    timeout=30,
                )

                if response.ok:
                    st.session_state["comparison_result"] = (
                        response.json()
                    )
                else:
                    st.error("Comparison failed.")
                    st.code(response.text)

            except (requests.RequestException, ValueError) as error:
                st.error(f"Comparison request failed: {error}")

result = st.session_state.get("comparison_result")

if result:
    left, right = st.columns(2)

    with left:
        st.subheader("Current")
        st.write(result["current_document"])
        st.write(f"Plan: {result['current_plan']}")

    with right:
        st.subheader("Proposed")
        st.write(result["proposed_document"])
        st.write(f"Plan: {result['proposed_plan']}")

    rows = result["clause_comparison"]

    st.subheader("Clause comparison")
    st.dataframe(
        pd.DataFrame(rows)[
            [
                "clause",
                "current_value",
                "proposed_value",
                "comparison_status",
                "explanation",
            ]
        ],
        hide_index=True,
    )

    for row in rows:
        with st.expander(f"Evidence: {row['clause']}"):
            for side in ["current", "proposed"]:
                st.markdown(
                    f"**{side.title()} — physical PDF page "
                    f"{row[f'{side}_page'] or 'not supplied'}**"
                )
                st.text(
                    row[f"{side}_evidence"]
                    or "No supporting quotation supplied."
                )
                st.write(
                    "Conditions:",
                    row[f"{side}_conditions"] or "None recorded.",
                )

    st.subheader("Amounts")
    if result["amount_comparison"]:
        st.dataframe(
            pd.DataFrame(result["amount_comparison"]),
            hide_index=True,
        )
    else:
        st.info(
            "No amount changes calculated. Both values and "
            "confirmation of comparability are required."
        )

    st.subheader("Questions for the insurer")
    for question in result["advisor_questions"]:
        st.write(f"• {question}")

    for warning in result["warnings"]:
        st.warning(warning)

    st.caption(f"Saved comparison ID: {result['analysis_id']}")
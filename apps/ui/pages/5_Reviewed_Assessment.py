import os

import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "COVERWISE_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="Reviewed Assessment",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Reviewed Assessment")
st.caption("Review completeness and confirmed restriction flags.")

st.info(
    "The score measures completion of three clause reviews. "
    "It does not measure policy quality or claim risk."
)

if st.button("Load saved reviews"):
    st.session_state.pop("assessment_result", None)
    st.session_state.pop("assessment_source", None)

    try:
        response = requests.get(
            f"{API_BASE_URL}/analyses",
            params={"limit": 100},
            timeout=10,
        )
        response.raise_for_status()

        st.session_state["assessment_reviews"] = [
            item
            for item in response.json()["analyses"]
            if item["analysis_type"] == "reviewed_policy"
        ]

    except (requests.RequestException, ValueError, KeyError) as error:
        st.session_state.pop("assessment_reviews", None)
        st.error(f"Could not load reviews: {error}")

reviews = st.session_state.get("assessment_reviews", [])

if not reviews:
    st.info("Save a policy review first, then load it here.")
else:
    labels = {
        item["analysis_id"]: (
            f"{item['created_at']} — {item['analysis_id'][:8]}"
        )
        for item in reviews
    }

    review_id = st.selectbox(
        "Policy review",
        list(labels),
        format_func=lambda value: labels[value],
    )

    if st.button("Open source review"):
        try:
            response = requests.get(
                f"{API_BASE_URL}/analyses/{review_id}",
                timeout=10,
            )
            response.raise_for_status()
            st.session_state["assessment_source"] = response.json()

        except (requests.RequestException, ValueError) as error:
            st.session_state.pop("assessment_source", None)
            st.error(f"Could not load source review: {error}")

    source = st.session_state.get("assessment_source")

    if source and source["analysis_id"] == review_id:
        st.write(
            f"**Document:** {source['result']['filename']} — "
            f"**Plan:** {source['result']['review']['selected_plan']}"
        )

        with st.expander("Reviewed values and supporting quotations"):
            st.json(source["result"]["review"])

        with st.form(f"assessment_form_{review_id}"):
            copay_known = st.checkbox(
                "Co-payment percentage is confirmed in the review"
            )
            copay = st.number_input(
                "Co-payment percentage",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
            )

            ped_known = st.checkbox(
                "PED waiting period is confirmed in the review"
            )
            ped_months = st.number_input(
                "PED waiting period in months",
                min_value=0,
                max_value=120,
                value=0,
            )

            room_selection = st.selectbox(
                "Confirmed room restriction",
                ["Unknown", "Yes", "No"],
            )

            st.caption(
                "Enter values only when supported by the saved review "
                "and applicable to its selected plan. "
                "General waiting periods are not automatically PED periods."
            )

            acknowledged = st.checkbox(
                "These structured values match my reviewed evidence "
                "and plan-specific conditions."
            )

            submitted = st.form_submit_button(
                "Calculate assessment",
                type="primary",
            )

        if submitted:
            st.session_state.pop("assessment_result", None)

            if not acknowledged:
                st.error("Acknowledge the reviewed values first.")
            else:
                payload = {
                    "review_id": review_id,
                    "copayment_percentage": copay if copay_known else None,
                    "ped_waiting_months": ped_months if ped_known else None,
                    "room_restriction_present": {
                        "Unknown": None,
                        "Yes": True,
                        "No": False,
                    }[room_selection],
                    "reviewer_acknowledged": True,
                }

                try:
                    response = requests.post(
                        f"{API_BASE_URL}/assessments",
                        json=payload,
                        timeout=30,
                    )

                    if response.ok:
                        st.session_state["assessment_result"] = (
                            response.json()
                        )
                    else:
                        st.error("Assessment failed.")
                        st.code(response.text)

                except (requests.RequestException, ValueError) as error:
                    st.error(f"Assessment request failed: {error}")

    result = st.session_state.get("assessment_result")

    if result and result["source_review_id"] == review_id:
        assessment = result["assessment"]

        st.metric(
            "Review completeness",
            f"{assessment['review_completeness_score']}/100",
        )
        st.caption(
            f"{assessment['confirmed_clause_groups']} of "
            "3 clause groups confirmed; not a coverage-quality score."
        )

        st.write(f"**Status:** {assessment['review_status']}")

        st.subheader("Restriction flags")
        if assessment["restriction_flags"]:
            for flag in assessment["restriction_flags"]:
                st.warning(flag)
        else:
            st.info(
                "No flags identified from the supplied signals. "
                "This does not establish unrestricted coverage."
            )

        st.subheader("Unresolved items")
        if assessment["unresolved_items"]:
            for item in assessment["unresolved_items"]:
                st.write(f"• {item}")
        else:
            st.write("None within this limited assessment scope.")

        with st.expander("Assessment limitations"):
            for item in assessment["limitations"]:
                st.write(f"• {item}")

        st.caption(f"Saved assessment ID: {result['analysis_id']}")
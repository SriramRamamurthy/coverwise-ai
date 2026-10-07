import os

import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "COVERWISE_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="CoverWise Reports",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Reports")
st.caption("Summaries and downloadable reports from saved analyses.")

if st.button("Load report sources"):
    st.session_state.pop("report_preview", None)
    st.session_state.pop("report_pdf", None)

    try:
        response = requests.get(
            f"{API_BASE_URL}/analyses",
            params={"limit": 100},
            timeout=10,
        )
        response.raise_for_status()

        st.session_state["report_sources"] = [
            item
            for item in response.json()["analyses"]
            if item["analysis_type"] in {
                "reviewed_policy",
                "policy_comparison",
                "review_assessment",
            }
        ]

    except (requests.RequestException, ValueError, KeyError) as error:
        st.session_state.pop("report_sources", None)
        st.error(f"Could not load sources: {error}")

sources = st.session_state.get("report_sources", [])

if not sources:
    st.info("Save a policy review or comparison, then load sources.")
else:
    labels = {
        item["analysis_id"]: (
            f"{item['analysis_type']} — "
            f"{item['created_at']} — "
            f"{item['analysis_id'][:8]}"
        )
        for item in sources
    }

    selected_id = st.selectbox(
        "Choose report source",
        list(labels),
        format_func=lambda value: labels[value],
    )

    if st.button("Prepare summary and PDF", type="primary"):
        st.session_state.pop("report_preview", None)
        st.session_state.pop("report_pdf", None)

        try:
            preview_response = requests.get(
                f"{API_BASE_URL}/reports/{selected_id}",
                timeout=30,
            )
            preview_response.raise_for_status()

            pdf_response = requests.get(
                f"{API_BASE_URL}/reports/{selected_id}/pdf",
                timeout=60,
            )
            pdf_response.raise_for_status()

            st.session_state["report_preview"] = (
                preview_response.json()
            )
            st.session_state["report_pdf"] = pdf_response.content

        except (requests.RequestException, ValueError) as error:
            st.error(f"Report preparation failed: {error}")

    report = st.session_state.get("report_preview")

    if report and report["analysis_id"] == selected_id:
        st.subheader("Summary")
        for line in report["summary"]:
            st.write(line)

        for section in report["sections"]:
            with st.expander(section["heading"]):
                for line in section["lines"]:
                    st.write(line)

        st.subheader("Advisor questions")
        for question in report["advisor_questions"]:
            st.write(f"• {question}")

        with st.expander("Limitations"):
            for limitation in report["limitations"]:
                st.write(f"• {limitation}")

        st.info(report["disclaimer"])

        st.download_button(
            "Download PDF report",
            data=st.session_state["report_pdf"],
            file_name=f"CoverWise_{selected_id}.pdf",
            mime="application/pdf",
        )
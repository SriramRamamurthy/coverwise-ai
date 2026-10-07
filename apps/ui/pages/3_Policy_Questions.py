import os

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "COVERWISE_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="Policy Questions",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 Policy Questions")
st.caption("Search uploaded policy text and inspect source passages.")

st.info(
    "This page retrieves evidence without an LLM. "
    "It does not generate or verify an insurance interpretation."
)

if st.button("Load saved documents"):
    st.session_state.pop("question_result", None)

    try:
        response = requests.get(
            f"{API_BASE_URL}/analyses",
            params={"limit": 100},
            timeout=10,
        )
        response.raise_for_status()

        st.session_state["question_documents"] = [
            record
            for record in response.json()["analyses"]
            if record["analysis_type"] == "pdf_extraction"
        ]

    except (requests.RequestException, ValueError, KeyError) as error:
        st.session_state.pop("question_documents", None)
        st.error(f"Could not load documents: {error}")

documents = st.session_state.get("question_documents", [])

if not documents:
    st.info("Extract a PDF on the main page, then load documents here.")

else:
    labels = {
        item["analysis_id"]: (
            f"{item['created_at']} — "
            f"{item['analysis_id'][:8]}"
        )
        for item in documents
    }

    st.dataframe(pd.DataFrame(documents), hide_index=True)

    document_id = st.selectbox(
        "Choose a document",
        options=list(labels),
        format_func=lambda value: labels[value],
    )

    st.caption(
        "Examples: What is the co-payment? "
        "What is the pre-existing disease waiting period? "
        "What room-rent limit is mentioned?"
    )

    with st.form("policy_question_form"):
        question = st.text_input(
            "Your policy question",
            max_chars=500,
        )

        submitted = st.form_submit_button(
            "Search document",
            type="primary",
        )

    if submitted:
        st.session_state.pop("question_result", None)

        if len(question.strip()) < 3:
            st.error("Enter a meaningful question.")
        else:
            try:
                with st.spinner("Searching policy passages..."):
                    response = requests.post(
                        f"{API_BASE_URL}/questions",
                        json={
                            "document_id": document_id,
                            "question": question.strip(),
                        },
                        timeout=30,
                    )

                if response.ok:
                    st.session_state["question_result"] = (
                        response.json()
                    )
                else:
                    st.error("Search failed.")
                    st.code(response.text)

            except (requests.RequestException, ValueError) as error:
                st.error(f"Search request failed: {error}")

    result = st.session_state.get("question_result")

    if result and result["source_analysis_id"] == document_id:
        st.subheader("Search result")
        st.write(f"**Document:** {result['filename']}")
        st.write(f"**Question:** {result['question']}")
        st.write(result["response"])

        if result["extraction_status"] == "partial":
            st.warning(
                "Some pages were unreadable. "
                "Search covers extracted text only."
            )

        for index, evidence in enumerate(result["evidence"], start=1):
            st.markdown(
                f"**Source {index}: {result['filename']} — "
                f"physical PDF page {evidence['page_number']}**"
            )
            st.text(evidence["excerpt"])
            st.caption(
                f"Keyword similarity: "
                f"{evidence['search_similarity']:.4f}; "
                "not answer confidence."
            )

        with st.expander("Search limitations"):
            for limitation in result["limitations"]:
                st.write(f"• {limitation}")

        st.caption(f"Saved question ID: {result['analysis_id']}")
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.coverwise.database import get_analysis, save_analysis


router = APIRouter(prefix="/questions", tags=["Policy questions"])


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    question: str = Field(min_length=3, max_length=500)


def normalize_search_text(text):
    text = text.lower()

    replacements = [
        (r"\bco[\s-]*pay(?:ment)?\b", "copayment"),
        (r"\bpre[\s-]*existing\b", "preexisting"),
        (r"\broom[\s-]+rent\b", "roomrent"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text


def build_chunks(pages):
    chunks = []

    for page in pages:
        text = re.sub(r"\s+", " ", page["text"]).strip()

        if not text:
            continue

        # Overlap preserves context around chunk boundaries.
        for start in range(0, len(text), 600):
            excerpt = text[start:start + 900]

            chunks.append(
                {
                    "page_number": page["page_number"],
                    "excerpt": excerpt,
                }
            )

            if start + 900 >= len(text):
                break

    return chunks


@router.post("")
def answer_from_passages(request: QuestionInput):
    question = request.question.strip()

    if len(question) < 3:
        raise HTTPException(
            status_code=422,
            detail="Enter a meaningful question.",
        )

    document = get_analysis(request.document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document["analysis_type"] != "pdf_extraction":
        raise HTTPException(
            status_code=400,
            detail="Select a saved PDF extraction.",
        )

    extraction = document["result"]
    chunks = build_chunks(extraction["pages"])
    evidence = []

    if chunks:
        texts = [
            normalize_search_text(chunk["excerpt"])
            for chunk in chunks
        ]

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )

        try:
            document_vectors = vectorizer.fit_transform(texts)
            question_vector = vectorizer.transform(
                [normalize_search_text(question)]
            )

            scores = cosine_similarity(
                question_vector,
                document_vectors,
            ).ravel()

            ranked = sorted(
                range(len(chunks)),
                key=lambda index: scores[index],
                reverse=True,
            )

            for index in ranked:
                if scores[index] <= 0:
                    continue

                candidate = chunks[index]

                # Avoid showing several overlapping chunks from one page.
                if any(
                    item["page_number"] == candidate["page_number"]
                    for item in evidence
                ):
                    continue

                evidence.append(
                    {
                        **candidate,
                        "search_similarity": round(
                            float(scores[index]), 4
                        ),
                    }
                )

                if len(evidence) == 3:
                    break

        except ValueError:
            # For example: the document contains no searchable vocabulary.
            evidence = []

    if evidence:
        response_text = (
            "Candidate passages are shown below. Review their conditions "
            "and applicability to your selected plan. Keyword similarity "
            "does not establish that a passage answers the question."
        )
        status = "candidate_evidence"
    else:
        response_text = (
            "No matching evidence was found by this keyword search. "
            "This does not establish that the policy lacks the term. "
            "Try different wording or review the document."
        )
        status = "no_keyword_evidence"

    decision_request = bool(
        re.search(
            r"\bshould\s+i\b|\brecommend\b|\bwhich.+better\b",
            question,
            flags=re.IGNORECASE,
        )
    )

    if decision_request:
        response_text = (
            "This application cannot make a final purchase, cancellation, "
            "or switching decision. Use the policy comparison and ask "
            "your insurer about relevant conditions. "
            + response_text
        )

    result = {
        "source_analysis_id": request.document_id,
        "filename": extraction["filename"],
        "question": question,
        "status": status,
        "response": response_text,
        "evidence": evidence,
        "extraction_status": extraction["extraction_status"],
        "extraction_warnings": extraction["warnings"],
        "method": "tfidf_keyword_retrieval",
        "limitations": [
            "No LLM or generated policy answer is used.",
            "Similarity is a search score, not answer confidence.",
            "Conditions may appear outside the displayed excerpts.",
            "Semantic search is not implemented yet.",
        ],
    }

    saved = save_analysis(
        inputs=request.model_dump(),
        result=result,
        analysis_type="policy_question",
    )

    return {**result, **saved}
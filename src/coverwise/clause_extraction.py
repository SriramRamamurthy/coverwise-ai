import re


CLAUSE_PATTERNS = {
    "copayment": {
        "label": "Co-payment",
        "pattern": r"\bco[\s-]*pay(?:ment)?\b",
        "question": (
            "What percentage applies, to whom, and under what conditions?"
        ),
    },
    "waiting_period": {
        "label": "Waiting periods",
        "pattern": (
            r"\bwaiting[\s-]+periods?\b"
            r"|\bpre[\s-]*existing\b"
        ),
        "question": (
            "Which waiting period is this: initial, "
            "pre-existing disease, or specific treatment?"
        ),
    },
    "room_rent": {
        "label": "Room-rent restrictions",
        "pattern": (
            r"\broom[\s-]+rent\b"
            r"|\broom[\s-]+(?:category|charges?|limits?)\b"
        ),
        "question": (
            "Is there a monetary cap or room-category restriction? "
            "What conditions and exceptions apply?"
        ),
    },
}

MAX_EVIDENCE_PER_FIELD = 6


def extract_clause_candidates(pages):
    findings = []

    for field_name, specification in CLAUSE_PATTERNS.items():
        pattern = re.compile(
            specification["pattern"],
            flags=re.IGNORECASE,
        )

        evidence = []
        seen = set()
        total_matches = 0

        for page in pages:
            # Normalize whitespace for readable excerpts.
            text = re.sub(r"\s+", " ", page.get("text", "")).strip()

            for match in pattern.finditer(text):
                total_matches += 1

                start = max(0, match.start() - 120)
                end = min(len(text), match.end() + 250)
                excerpt = text[start:end]

                evidence_key = (page["page_number"], excerpt)

                if evidence_key in seen:
                    continue

                seen.add(evidence_key)

                if len(evidence) < MAX_EVIDENCE_PER_FIELD:
                    evidence.append(
                        {
                            "page_number": page["page_number"],
                            "matched_phrase": match.group(),
                            "excerpt": excerpt,
                        }
                    )

        findings.append(
            {
                "field": field_name,
                "label": specification["label"],
                "status": (
                    "needs_review" if evidence else "not_found"
                ),
                "confirmed_value": None,
                "evidence": evidence,
                "keyword_matches": total_matches,
                "evidence_display_limited": (
                    len(seen) > MAX_EVIDENCE_PER_FIELD
                ),
                "review_question": specification["question"],
            }
        )

    return {
        "findings": findings,
        "method": "keyword_patterns_v1",
        "limitations": [
            "Keyword matches identify candidate passages, not policy facts.",
            "Values and applicability require review of the original PDF.",
            "Not found does not mean excluded, absent, or unrestricted.",
            "Excerpts may omit conditions elsewhere in the document.",
            "Each field displays at most six candidate excerpts.",
        ],
    }
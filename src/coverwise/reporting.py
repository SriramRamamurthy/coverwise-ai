from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_report_content(record):
    result = record["result"]
    sections = []

    # Build an assessment report from its underlying policy review.
    if record["analysis_type"] == "review_assessment":
        assessment = result["assessment"]

        report = build_report_content({
            **record,
            "analysis_type": "reviewed_policy",
            "result": result["reviewed_policy"],
        })

        report["report_type"] = "review_assessment"
        report["summary"] = [
            line
            for line in report["summary"]
            if not line.startswith("Coverage score:")
        ]

        report["summary"].extend([
            (
                "Review completeness: "
                f"{assessment['review_completeness_score']}/100 "
                "(not coverage quality)"
            ),
            f"Review status: {assessment['review_status']}",
        ])

        assessment_lines = [
            (
                "Confirmed clause groups: "
                f"{assessment['confirmed_clause_groups']}/"
                f"{assessment['total_clause_groups']}"
            ),
        ]

        if assessment["restriction_flags"]:
            assessment_lines.extend(assessment["restriction_flags"])
        else:
            assessment_lines.append(
                "No flags identified from supplied signals. "
                "This does not establish unrestricted coverage."
            )

        if assessment["unresolved_items"]:
            assessment_lines.extend(
                f"Unresolved: {item}"
                for item in assessment["unresolved_items"]
            )
        else:
            assessment_lines.append(
                "No unresolved items within this limited assessment scope."
            )

        report["sections"].append({
            "heading": "Review completeness and restrictions",
            "lines": assessment_lines,
        })

        report["sections"].append({
            "heading": "Structured assessment inputs",
            "lines": [
                (
                    f"{name}: "
                    f"{value if value is not None else 'Not supplied'}"
                )
                for name, value in assessment["structured_inputs"].items()
            ],
        })

        # Replace the preliminary scoring note for assessed reports.
        report["limitations"] = [
            item
            for item in report["limitations"]
            if item != "No coverage score is calculated at this stage."
        ]
        report["limitations"].extend(assessment["limitations"])

        report["sections"].append({
            "heading": "Traceability",
            "lines": [
                f"Source review ID: {result['source_review_id']}",
                (
                    "Assessment values are user-confirmed and should "
                    "be checked against the source review."
                ),
            ],
        })

        return report

    if record["analysis_type"] == "reviewed_policy":
        review = result["review"]

        summary = [
            f"Source document: {result['filename']}",
            f"Selected plan: {review['selected_plan']}",
            (
                "User age: "
                f"{review['age'] if review['age'] is not None else 'Not supplied'}"
            ),
            f"Family details: {review['family_details'] or 'Not supplied'}",
            (
                "Coverage concern: "
                f"{review['coverage_requirement'] or 'Not supplied'}"
            ),
            (
                "Annual premium, user supplied: "
                f"{review['annual_premium'] if review['annual_premium'] is not None else 'Not supplied'}"
            ),
            (
                "Sum insured, user supplied: "
                f"{review['sum_insured'] if review['sum_insured'] is not None else 'Not supplied'}"
            ),
            f"Text extraction status: {result['extraction_status']}",
        ]

        for key, label in [
            ("copayment", "Co-payment"),
            ("waiting_period", "Waiting periods"),
            ("room_rent", "Room rent"),
        ]:
            clause = review[key]

            summary.append(
                f"{label}: {clause['value'] or 'Not confirmed'} "
                f"({clause['status']})"
            )

            sections.append({
                "heading": label,
                "lines": [
                    f"Review status: {clause['status']}",
                    (
                        "Interpretation: "
                        f"{clause['value'] or 'Not confirmed'}"
                    ),
                    (
                        "Conditions: "
                        f"{clause['conditions'] or 'None recorded'}"
                    ),
                    (
                        f"Source: {result['filename']}, "
                        "physical PDF page "
                        f"{clause['source_page'] or 'not supplied'}"
                    ),
                    (
                        "Supporting quotation: "
                        f"{clause['evidence'] or 'Not supplied'}"
                    ),
                ],
            })

        summary.append(
            "Coverage score: not calculated for this review. "
            "Use the separate reviewed assessment for completeness scoring."
        )

        sections.append({
            "heading": "Document traceability",
            "lines": [
                (
                    "Source PDF analysis ID: "
                    f"{result['source_analysis_id']}"
                ),
                f"Document SHA-256: {result['document_hash']}",
            ],
        })

        questions = [
            "Confirm the reviewed terms apply to the selected plan.",
            "Explain co-payment triggers and exceptions.",
            "Confirm each waiting period and any continuity credits.",
            "Explain room-category limits and proportionate deductions.",
            "Confirm family eligibility and any relevant exclusions.",
        ]

        limitations = list(result["limitations"])

    elif record["analysis_type"] == "policy_comparison":
        summary = [
            f"Current document: {result['current_document']}",
            f"Current plan: {result['current_plan']}",
            f"Proposed document: {result['proposed_document']}",
            f"Proposed plan: {result['proposed_plan']}",
            "Comparison uses saved, user-reviewed interpretations.",
            "The current comparison covers three clause groups.",
        ]

        for row in result["clause_comparison"]:
            summary.append(
                f"{row['clause']}: {row['comparison_status']}"
            )

            sections.append({
                "heading": row["clause"],
                "lines": [
                    f"Comparison: {row['comparison_status']}",
                    row["explanation"],
                    (
                        "Current interpretation: "
                        f"{row['current_value']}"
                    ),
                    (
                        "Proposed interpretation: "
                        f"{row['proposed_value']}"
                    ),
                    (
                        "Current conditions: "
                        f"{row['current_conditions'] or 'None recorded'}"
                    ),
                    (
                        "Proposed conditions: "
                        f"{row['proposed_conditions'] or 'None recorded'}"
                    ),
                    (
                        f"Current source: {result['current_document']}, "
                        "physical PDF page "
                        f"{row['current_page'] or 'not supplied'}"
                    ),
                    (
                        "Current quotation: "
                        f"{row['current_evidence'] or 'Not supplied'}"
                    ),
                    (
                        f"Proposed source: {result['proposed_document']}, "
                        "physical PDF page "
                        f"{row['proposed_page'] or 'not supplied'}"
                    ),
                    (
                        "Proposed quotation: "
                        f"{row['proposed_evidence'] or 'Not supplied'}"
                    ),
                ],
            })

        if result["amount_comparison"]:
            sections.append({
                "heading": "User-supplied amounts",
                "lines": [
                    (
                        f"{item['field']}: "
                        f"current {item['current']}; "
                        f"proposed {item['proposed']}; "
                        f"change {item['change_percentage']}%."
                    )
                    for item in result["amount_comparison"]
                ],
            })

        sections.append({
            "heading": "Review traceability",
            "lines": [
                f"Current review ID: {result['current_review_id']}",
                f"Proposed review ID: {result['proposed_review_id']}",
            ],
        })

        summary.extend([
            "Amount changes do not establish policy value.",
            "Coverage-quality scores are not calculated.",
            "Insurer confirmation is required before switching.",
        ])

        questions = list(result["advisor_questions"])
        limitations = list(result["warnings"])

    else:
        raise ValueError(
            "Reports support reviewed policies, comparisons, "
            "and reviewed assessments only."
        )

    return {
        "analysis_id": record["analysis_id"],
        "created_at": record["created_at"],
        "report_type": record["analysis_type"],
        "summary": summary,
        "sections": sections,
        "advisor_questions": questions,
        "limitations": limitations,
        "disclaimer": (
            "This prototype supports policy understanding only. "
            "It is not final financial, legal, medical, or insurance "
            "advice. Confirm interpretations with your insurer or advisor."
        ),
    }


def render_pdf(report):
    buffer = BytesIO()
    styles = getSampleStyleSheet()

    styles["BodyText"].fontSize = 10
    styles["BodyText"].leading = 14
    styles["BodyText"].spaceAfter = 7

    story = []

    def add(text, style="BodyText"):
        # Display unsupported characters explicitly rather than
        # allowing missing glyphs in the basic PDF font.
        safe_text = str(text).encode(
            "ascii",
            errors="backslashreplace",
        ).decode("ascii")

        story.append(
            Paragraph(
                escape(safe_text).replace("\n", "<br/>"),
                styles[style],
            )
        )

    add("CoverWise Policy Understanding Report", "Title")
    add(f"Analysis ID: {report['analysis_id']}")
    add(f"Analysis created: {report['created_at']}")
    add(f"Report type: {report['report_type']}")
    add(report["disclaimer"])

    add("Policy summary", "Heading2")
    for line in report["summary"]:
        add(line)

    for section in report["sections"]:
        add(section["heading"], "Heading2")

        for line in section["lines"]:
            add(line)

        story.append(Spacer(1, 8))

    add("Questions for the insurer or advisor", "Heading2")
    for number, question in enumerate(
        report["advisor_questions"],
        start=1,
    ):
        add(f"{number}. {question}")

    add("Limitations", "Heading2")
    for limitation in report["limitations"]:
        add(limitation)

    add(
        "Rendering note: non-ASCII characters use escape notation "
        "in this initial PDF exporter. Original quotations remain "
        "available in the application. Page references are physical "
        "PDF page numbers."
    )

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title="CoverWise Policy Understanding Report",
    )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            42,
            24,
            "CoverWise - decision-support prototype",
        )
        canvas.drawRightString(
            A4[0] - 42,
            24,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )

    return buffer.getvalue()
import hashlib
from io import BytesIO

from pypdf import PdfReader


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGES = 100


class PDFProcessingError(ValueError):
    pass


def extract_pdf_text(content, filename):
    if not content:
        raise PDFProcessingError("The uploaded file is empty.")

    if len(content) > MAX_UPLOAD_BYTES:
        raise PDFProcessingError("Maximum PDF size is 10 MB.")

    if b"%PDF-" not in content[:1024]:
        raise PDFProcessingError("The file does not have a PDF header.")

    try:
        reader = PdfReader(BytesIO(content))

        if reader.is_encrypted:
            raise PDFProcessingError(
                "Encrypted PDFs are not supported in this version."
            )

        page_count = len(reader.pages)

        if page_count == 0:
            raise PDFProcessingError("The PDF contains no pages.")

        if page_count > MAX_PAGES:
            raise PDFProcessingError(
                f"Maximum supported document length is {MAX_PAGES} pages."
            )

        pages = []
        warnings = []

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
                status = "text_extracted" if text else "no_text"

                if not text:
                    warnings.append(
                        f"Page {page_number}: no readable text found. "
                        "It may be scanned, blank, or unsupported."
                    )

            except Exception:
                text = ""
                status = "extraction_failed"
                warnings.append(
                    f"Page {page_number}: text extraction failed."
                )

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "character_count": len(text),
                    "status": status,
                }
            )

        readable_pages = sum(
            page["status"] == "text_extracted"
            for page in pages
        )

        if readable_pages == 0:
            raise PDFProcessingError(
                "No readable text was found. "
                "Try a text-based PDF. OCR is not implemented yet."
            )

        return {
            "filename": filename,
            "document_hash": hashlib.sha256(content).hexdigest(),
            "page_count": page_count,
            "readable_pages": readable_pages,
            "extraction_status": (
                "complete"
                if readable_pages == page_count
                else "partial"
            ),
            "pages": pages,
            "warnings": warnings,
            "page_numbering": (
                "Physical PDF page numbers, starting at 1; "
                "these may differ from printed page labels."
            ),
        }

    except PDFProcessingError:
        raise
    except Exception as error:
        raise PDFProcessingError(
            "The PDF could not be read. It may be damaged or unsupported."
        ) from error
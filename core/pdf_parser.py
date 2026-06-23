"""pdf_parser.py — estrae testo da PDF via PyMuPDF."""

import fitz
import io


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)

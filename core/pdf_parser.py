import fitz
import io


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Estrae tutto il testo da un PDF (bytes)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)


def extract_text_from_path(path: str) -> str:
    with open(path, "rb") as f:
        return extract_text_from_pdf(f.read())

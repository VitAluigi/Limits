"""pdf_parser.py — estrae testo da PDF via PyMuPDF, con fallback OCR.

Molti rendiconti / regolamenti sono PDF *scansionati* (immagine, senza layer
di testo): in quel caso get_text("text") restituisce stringa vuota. Se una
pagina non ha testo selezionabile si attiva l'OCR (tesseract, lingua italiana).
"""

import os
import fitz  # PyMuPDF


def _tessdata() -> str | None:
    """Individua la cartella tessdata (necessaria a PyMuPDF per l'OCR)."""
    if os.environ.get("TESSDATA_PREFIX"):
        return os.environ["TESSDATA_PREFIX"]
    for p in (
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tesseract-ocr/4.00/tessdata",
        "/usr/share/tessdata",
    ):
        if os.path.isdir(p):
            return p
    return None


def _page_text(page) -> str:
    """Testo della pagina; se manca il layer di testo ripiega su OCR."""
    t = page.get_text("text")
    if len(t.strip()) >= 20:
        return t
    try:
        kw = dict(language="ita", dpi=200, full=True)
        td = _tessdata()
        if td:
            kw["tessdata"] = td
        tp = page.get_textpage_ocr(**kw)
        return page.get_text("text", textpage=tp)
    except Exception:
        return t


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [_page_text(page) for page in doc]
    doc.close()
    return "\n".join(pages)

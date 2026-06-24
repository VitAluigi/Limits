"""
rendiconto_parser.py
Estrae dal Rendiconto dei fondi interni assicurativi (schema IVASS - Allegato 1,
Situazione Patrimoniale) i valori di base per ciascun fondo:

  - totale_attivita : "TOTALE ATTIVITA'"  -> base per i limiti 474 espressi come
                      "% del totale delle attività assegnate al fondo"
  - nav             : Valore complessivo netto del fondo -> base per i limiti
                      espressi come "% del valore corrente / complessivo del fondo"
                      e per i comparti del regolamento.

Robustezza:
  * PDF SCANSIONATI (senza layer di testo): fallback OCR via tesseract (lingua ita).
  * LAYOUT A COLONNE / OCR: gli importi possono trovarsi su righe successive
    all'etichetta -> _first_euro_after guarda anche le righe seguenti.
  * NAV: si legge preferibilmente dalla riga "VALORE COMPLESSIVO NETTO";
    se assente (OCR che salta la riga) si ricava per differenza (att - pass).
"""

from __future__ import annotations
import os
import re
import fitz  # PyMuPDF

# Confine fra i blocchi (sia Situazione Patrimoniale sia Sezione Reddituale)
_BOUND = re.compile(r"RENDICONTO DEL FONDO INTERNO", re.IGNORECASE)

# Header del blocco patrimoniale: cattura nome fondo e data
_HDR = re.compile(
    r"RENDICONTO DEL FONDO INTERNO\s+(.*?)\s+SITUAZIONE PATRIMONIALE\s+AL\s+([\d/.\-]+)",
    re.IGNORECASE | re.DOTALL,
)

# Importi in formato italiano: 1.234.567,89  (le percentuali "100,00" vengono scartate)
_NUM = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


# ---------------------------------------------------------------------------
# OCR fallback
# ---------------------------------------------------------------------------

def _tessdata() -> str | None:
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


# ---------------------------------------------------------------------------
# Estrazione importi
# ---------------------------------------------------------------------------

def _euros(line: str) -> list[float]:
    """Valori monetari della riga, esclusi i '100,00' (percentuali di totale)."""
    out = []
    for v in _NUM.findall(line):
        if v == "100,00":
            continue
        out.append(float(v.replace(".", "").replace(",", ".")))
    return out


def _first_euro_after(block: str, label_prefix: str, lookahead: int = 4) -> float | None:
    """
    Primo importo (= colonna periodo corrente) della riga che inizia con
    label_prefix; se sulla riga dell'etichetta non ci sono numeri (layout a
    colonne / OCR), cerca nelle righe immediatamente successive.
    """
    label_prefix = label_prefix.upper()
    lines = block.splitlines()
    for i, raw in enumerate(lines):
        s = raw.strip().upper()
        if s.startswith(label_prefix):
            for j in range(i, min(i + 1 + lookahead, len(lines))):
                vals = _euros(lines[j])
                if vals:
                    return vals[0]
    return None


def parse_rendiconto(pdf_bytes: bytes) -> dict[str, dict]:
    """
    Restituisce {nome_fondo: {nome_fondo, data, totale_attivita, totale_passivita, nav}}.
    In caso di nomi duplicati mantiene la prima occorrenza.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(_page_text(page) for page in doc)
    doc.close()

    bounds = [m.start() for m in _BOUND.finditer(text)] + [len(text)]
    fondi: dict[str, dict] = {}

    for i in range(len(bounds) - 1):
        block = text[bounds[i]:bounds[i + 1]]
        m = _HDR.search(block)
        if not m:
            # blocco "SEZIONE REDDITUALE" o altro: ignorato
            continue

        nome = re.sub(r"\s+", " ", m.group(1)).strip().strip("-– ").strip()
        data = m.group(2).strip()

        tot = _first_euro_after(block, "TOTALE ATTIVIT")
        if tot is None:
            continue

        nav = _first_euro_after(block, "VALORE COMPLESSIVO NETTO")
        pas = _first_euro_after(block, "TOTALE PASSIVIT")
        if nav is None and pas is not None:
            nav = tot - abs(pas)

        if nome and nome not in fondi:
            fondi[nome] = {
                "nome_fondo": nome,
                "data": data,
                "totale_attivita": round(tot, 2),
                "totale_passivita": round(abs(pas), 2) if pas is not None else None,
                "nav": round(nav, 2) if nav is not None else None,
            }

    return fondi


# ---------------------------------------------------------------------------
# Abbinamento nome fondo SHIP <-> nome fondo rendiconto
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = str(s).upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_fondo(nome_ship: str, fondi_rendiconto: dict[str, dict]) -> dict | None:
    """
    Trova nel rendiconto il fondo corrispondente al nome SHIP selezionato.
    1) match esatto normalizzato; 2) contenimento; 3) maggiore sovrapposizione di token.
    """
    if not nome_ship or not fondi_rendiconto:
        return None

    target = _norm(nome_ship)
    norm_map = {k: _norm(k) for k in fondi_rendiconto}

    for k, n in norm_map.items():
        if n == target:
            return fondi_rendiconto[k]

    for k, n in norm_map.items():
        if target and (target in n or n in target):
            return fondi_rendiconto[k]

    t_tokens = set(target.split())
    best, best_score = None, 0
    for k, n in norm_map.items():
        score = len(t_tokens & set(n.split()))
        if score > best_score:
            best, best_score = k, score
    return fondi_rendiconto[best] if best and best_score >= 2 else None

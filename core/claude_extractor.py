import anthropic
import json
import re
import streamlit as st

MODEL = "claude-sonnet-4-20250514"

def _get_client():
    return anthropic.Anthropic(api_key=st.secrets["CLAUDE_API_KEY"])

PROMPT_LIMITI_REG38 = """Sei un esperto di normativa assicurativa italiana. 
Analizza il testo del Regolamento IVASS n.38 fornito ed estrai TUTTI i limiti quantitativi 
sugli investimenti delle gestioni separate e fondi interni assicurativi.

Per ogni limite estrai:
- categoria_asset: la categoria di attivo (es. "Titoli di Stato", "Obbligazioni corporate", "Azioni quotate", ecc.)
- codice_ivass: eventuale codice/riferimento IVASS (es. "Art. 10 comma 2")
- limite_max_pct: limite massimo in % del portafoglio (null se non previsto)
- limite_min_pct: limite minimo in % (null se non previsto)
- limite_emittente_pct: limite per singolo emittente in % (null se non previsto)
- limite_controparte_pct: limite per singola controparte (null se non previsto)
- note: eventuali condizioni o eccezioni importanti
- articolo: articolo di riferimento

Rispondi SOLO con un array JSON valido, nessun testo aggiuntivo, nessun markdown.
Esempio formato:
[
  {
    "categoria_asset": "Titoli di Stato UE",
    "codice_ivass": "Art. 10 c.1",
    "limite_max_pct": null,
    "limite_min_pct": null,
    "limite_emittente_pct": 35.0,
    "limite_controparte_pct": null,
    "note": "Derogabile fino al 100% per titoli garantiti dallo Stato",
    "articolo": "Art. 10"
  }
]

TESTO REGOLAMENTO N.38:
{testo}
"""

PROMPT_LIMITI_REGOLAMENTO = """Sei un esperto di gestioni separate e fondi interni assicurativi italiani.
Analizza il regolamento della gestione/fondo fornito ed estrai TUTTI i limiti di investimento 
specifici previsti dal regolamento stesso (non quelli di legge).

Per ogni limite estrai:
- categoria_asset: la categoria di attivo
- limite_max_pct: limite massimo in % (null se non previsto)
- limite_min_pct: limite minimo in % (null se non previsto)
- limite_emittente_pct: limite per singolo emittente in % (null se non previsto)
- limite_controparte_pct: limite per singola controparte (null se non previsto)
- note: condizioni specifiche
- sezione: sezione/articolo del regolamento

Rispondi SOLO con un array JSON valido, nessun testo aggiuntivo, nessun markdown.

TESTO REGOLAMENTO GESTIONE:
{testo}
"""

PROMPT_NOME_GESTIONE = """Dal testo del regolamento assicurativo fornito, estrai:
- nome_gestione: il nome completo della gestione separata o del fondo
- tipo: "gestione_separata" o "fondo_interno"
- compagnia: nome della compagnia assicurativa (se presente)

Rispondi SOLO con un oggetto JSON valido, nessun testo aggiuntivo.
Esempio: {{"nome_gestione": "GESAV", "tipo": "gestione_separata", "compagnia": "Generali"}}

TESTO:
{testo}
"""

def _call_claude(prompt: str, max_tokens: int = 4096) -> str:
    msg = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

def _parse_json_safe(text: str):
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)

def estrai_limiti_reg38(testo_pdf: str) -> list[dict]:
    """Estrae limiti dal Reg. IVASS n.38."""
    testo = testo_pdf[:80000]
    risposta = _call_claude(PROMPT_LIMITI_REG38.format(testo=testo), max_tokens=4096)
    return _parse_json_safe(risposta)

def estrai_limiti_regolamento(testo_pdf: str) -> list[dict]:
    """Estrae limiti dal regolamento della gestione."""
    testo = testo_pdf[:80000]
    risposta = _call_claude(PROMPT_LIMITI_REGOLAMENTO.format(testo=testo), max_tokens=4096)
    return _parse_json_safe(risposta)

def estrai_info_gestione(testo_pdf: str) -> dict:
    """Estrae nome e tipo della gestione dal regolamento."""
    testo = testo_pdf[:10000]
    risposta = _call_claude(PROMPT_NOME_GESTIONE.format(testo=testo), max_tokens=512)
    return _parse_json_safe(risposta)

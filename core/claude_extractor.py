"""
claude_extractor.py
Estrae limiti quantitativi dai PDF di normativa e regolamento via Claude API.
"""

import json
import re
import anthropic
import streamlit as st

MODEL = "claude-sonnet-4-6"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=st.secrets["CLAUDE_API_KEY"])


def _call(prompt: str, max_tokens: int = 4096) -> str:
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _parse_json(text: str):
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if m:
        text = m.group(1)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Prompt per il regolamento del fondo
# ---------------------------------------------------------------------------

PROMPT_REGOLAMENTO = """Sei un esperto di fondi interni assicurativi italiani (Unit Linked).
Analizza il testo del regolamento del fondo fornito ed estrai TUTTI i limiti quantitativi
di investimento previsti (non quelli di legge ma quelli specifici del fondo).
Per ogni limite estrai:
- categoria_asset: la categoria di attivo (es. "Investimenti obbligazionari", "Investimenti azionari")
- limite_max_pct: limite massimo in % del fondo (null se non previsto)
- limite_min_pct: limite minimo in % (null se non previsto)
- limite_emittente_pct: limite per singolo emittente in % (null se non previsto)
- limite_controparte_pct: limite per singola controparte (null se non previsto)
- note: condizioni o eccezioni rilevanti
- sezione: sezione/paragrafo del regolamento

Rispondi SOLO con un array JSON valido, nessun testo aggiuntivo, nessun markdown.

TESTO REGOLAMENTO:
{testo}
"""

# ---------------------------------------------------------------------------
# Prompt per il nome/info del fondo
# ---------------------------------------------------------------------------

PROMPT_INFO_FONDO = """Dal testo del regolamento assicurativo fornito, estrai:
- nome_fondo: il nome completo del fondo interno
- tipo: "fondo_interno_ul" oppure "gestione_separata" oppure "fondo_pensione"
- compagnia: nome della compagnia assicurativa (se presente)
- tipo_prestazione: "non_previdenziale" oppure "previdenziale" (se desumibile)

Rispondi SOLO con un oggetto JSON valido, nessun testo aggiuntivo.
Esempio: {{"nome_fondo": "DM Global Equity", "tipo": "fondo_interno_ul",
           "compagnia": "Fondo UL 1 S.p.A.", "tipo_prestazione": "non_previdenziale"}}

TESTO:
{testo}
"""


def estrai_limiti_regolamento(testo_pdf: str) -> list[dict]:
    prompt = PROMPT_REGOLAMENTO.replace("{testo}", testo_pdf[:80000])
    risposta = _call(prompt, max_tokens=4096)
    return _parse_json(risposta)


def estrai_info_fondo(testo_pdf: str) -> dict:
    prompt = PROMPT_INFO_FONDO.replace("{testo}", testo_pdf[:10000])
    risposta = _call(prompt, max_tokens=512)
    return _parse_json(risposta)

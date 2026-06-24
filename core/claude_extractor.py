"""
claude_extractor.py
Estrae limiti quantitativi dai PDF di regolamento via Claude API.
Ogni limite riporta anche la BASE DI CALCOLO su cui va verificato.
"""
import json
import re
import anthropic
import streamlit as st

MODEL = "claude-sonnet-4-6"   # stringa API valida (in precedenza "claude-opus-4-6" -> 404)


def _client() -> anthropic.Anthropic:
    key = st.secrets.get("CLAUDE_API_KEY")
    if not key:
        raise RuntimeError("CLAUDE_API_KEY non configurata nei secrets di Streamlit.")
    return anthropic.Anthropic(api_key=key)


def _call(prompt: str, max_tokens: int = 8192) -> str:
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    # robusto a più blocchi / tool use
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def _parse_json(text: str):
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if m:
        text = m.group(1)
    return json.loads(text)


PROMPT_REGOLAMENTO = """Sei un esperto di fondi interni assicurativi italiani (Unit Linked).
Analizza il testo del regolamento e estrai TUTTI i limiti quantitativi di investimento
specifici del fondo (non quelli di legge). Per ogni limite estrai:
- categoria_asset: la categoria di attivo (es. "Monetario", "Obbligazionario", "Azionario", "Azionario Tecnologico", "Bilanciato", "Flessibile", "Liquidità")
- limite_max_pct: limite massimo in % (null se non previsto)
- limite_min_pct: limite minimo in % (null se non previsto)
- limite_emittente_pct: limite per singolo emittente in % (null se non previsto)
- limite_controparte_pct: limite per singola controparte (null se non previsto)
- base_calcolo: la grandezza a cui la percentuale è riferita. Usa uno fra:
    "patrimonio"  -> "% del patrimonio / del Fondo / valore complessivo / NAV"
    "attivo"      -> "% del totale delle attività"
    "categoria"   -> "% della categoria / del comparto" (sub-limiti interni)
  Se non specificato, per i comparti di asset allocation usa "patrimonio".
- note: condizioni o eccezioni rilevanti
- sezione: indica SEMPRE in questo formato esatto: "<Articolo/paragrafo> - <Nome del Fondo Interno a cui il limite si riferisce>"
  (es. "Art. 4 - DM Global Equity"). Il nome del fondo è obbligatorio quando il
  regolamento contiene più fondi interni distinti.

Rispondi SOLO con un array JSON valido, nessun testo aggiuntivo, nessun markdown.
TESTO REGOLAMENTO:
{testo}
"""

PROMPT_INFO_FONDO = """Dal testo del regolamento assicurativo estrai:
- nome_fondo: il nome completo del fondo interno (o della famiglia di fondi)
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
    risposta = _call(prompt, max_tokens=8192)
    data = _parse_json(risposta)
    if isinstance(data, dict):
        # singolo oggetto o wrapper {"limiti": [...]}
        for v in data.values():
            if isinstance(v, list):
                return v
        return [data]
    return data if isinstance(data, list) else []


def estrai_info_fondo(testo_pdf: str) -> dict:
    prompt = PROMPT_INFO_FONDO.replace("{testo}", testo_pdf[:10000])
    risposta = _call(prompt, max_tokens=512)
    data = _parse_json(risposta)
    return data if isinstance(data, dict) else {}

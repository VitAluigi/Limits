"""
app.py
"""

import streamlit as st
import pandas as pd
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pdf_parser import extract_text_from_pdf
from core.claude_extractor import estrai_limiti_regolamento, estrai_info_fondo
from core.ship_parser import load_ship, get_fondi, filter_portafoglio
from core.excel_writer import genera_excel
from core.rendiconto_parser import parse_rendiconto, match_fondo
from core.analisi import (
    esegui_tutti_check, check_regolamento, CheckResult, Basi, BASE_LABEL,
)

# -- Page config --------------------------------------------------------------
st.set_page_config(
    page_title="Verifica Limiti UL - 474/D",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {
    background-color: #00338D;
}
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 { color: white; }
[data-testid="stSidebar"] { background-color: rgb(0, 40, 110); }
.main-title { font-size:1.8rem; font-weight:700; color:#FFFFFF; margin-bottom:.2rem; }
.sub-title  { font-size:1rem;  color:#5A5A5A;  margin-bottom:1.5rem; }
div[data-testid="stDownloadButton"] button {
    background-color:#00338D; color:white; font-weight:600;
    border-radius:6px; padding:.5rem 1.5rem; width:100%;
}
.esito-ok   { color:#276221; font-weight:700; }
.esito-err  { color:#9C0006; font-weight:700; }
.esito-warn { color:#7D6608; font-weight:700; }
.esito-gray { color:#595959; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Verifica Limiti Fondi Interni UL</div>',
            unsafe_allow_html=True)
st.markdown('<div class="sub-title">Circolare ISVAP 474/D - Regolamento fondo</div>',
            unsafe_allow_html=True)

# -- Session state -------------------------------------------------------------
for k in ["df_ship", "limiti_reg", "info_fondo", "results_474", "results_reg",
          "excel_bytes", "nome_fondo", "rendiconto", "basi"]:
    if k not in st.session_state:
        st.session_state[k] = None


# -- Helper: nome fondo dal campo "sezione" ("Art. X - <Nome fondo>") ----------
def _fondo_da_sezione(sezione: str) -> str:
    s = str(sezione or "")
    if " - " in s:
        return s.split(" - ", 1)[1].strip()
    return s.strip()


# -- SIDEBAR -------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Caricamento file")
    st.divider()

    # 1. Regolamento fondo
    st.markdown("**Regolamento del fondo** *(opzionale)*")
    pdf_reg = st.file_uploader("PDF regolamento", type=["pdf"],
                               key="up_reg", label_visibility="collapsed")
    if pdf_reg:
        if st.button("Estrai limiti regolamento", use_container_width=True):
            with st.spinner("Analisi PDF con AI…"):
                try:
                    testo = extract_text_from_pdf(pdf_reg.read())
                    st.session_state.limiti_reg = estrai_limiti_regolamento(testo)
                    st.session_state.info_fondo = estrai_info_fondo(testo)
                    n = len(st.session_state.limiti_reg)
                    nome = st.session_state.info_fondo.get("nome_fondo", "-")
                    st.success(f"Estratti {n} limiti - Fondo: **{nome}**")
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.divider()

    # 2. Portafoglio SHIP
    st.markdown("**Portafoglio del fondo** *(obbligatorio)*")
    ship_file = st.file_uploader("File Posizioni (.xlsx)", type=["xlsx", "xls"],
                                 key="up_ship", label_visibility="collapsed")
    if ship_file:
        if st.button("Carica portafoglio", use_container_width=True):
            with st.spinner("Parsing SHIP…"):
                try:
                    df = load_ship(ship_file.read())
                    st.session_state.df_ship = df
                    fondi = get_fondi(df)
                    st.success(f"{len(df):,} posizioni - {len(fondi)} fondi")
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.divider()

    # 3. Rendiconto (basi di calcolo)
    st.markdown("**Rendiconto del fondo** *(opzionale, per le basi di calcolo)*")
    pdf_rend = st.file_uploader("PDF rendiconto (Allegato 1)", type=["pdf"],
                                key="up_rend", label_visibility="collapsed")
    if pdf_rend and st.button("Estrai basi dal rendiconto", use_container_width=True):
        with st.spinner("Parsing rendiconto…"):
            try:
                st.session_state.rendiconto = parse_rendiconto(pdf_rend.read())
                # reset della selezione/basi per riallineare ai nuovi fondi estratti
                st.session_state.pop("_last_fondo_rend", None)
                st.session_state.pop("man_tot", None)
                st.session_state.pop("man_nav", None)
                st.success(
                    f"Estratti {len(st.session_state.rendiconto)} fondi dal rendiconto")
            except Exception as e:
                st.error(f"Errore: {e}")

    st.divider()

    # 4. Parametri check 474
    st.markdown("**Parametri 474/D**")
    tipo_fondo = st.selectbox("Tipo fondo",
                              ["non previdenziale", "previdenziale"],
                              key="tipo_fondo")
    limite_nq = 10.0 if tipo_fondo == "non previdenziale" else 25.0
    st.caption(f"Limite non quotati applicato: **{limite_nq}%**")


# -- MAIN ----------------------------------------------------------------------

# Stato caricamento
col_s1, col_s2 = st.columns(2)
with col_s1:
    ok_ship = st.session_state.df_ship is not None
    n_pos = len(st.session_state.df_ship) if ok_ship else 0
    st.markdown(
        f"{'✅' if ok_ship else '❌'} **Portafoglio** - "
        f"{'**' + str(n_pos) + ' posizioni**' if ok_ship else '_non caricato_'}"
    )
with col_s2:
    ok_reg = st.session_state.limiti_reg is not None
    n_lim = len(st.session_state.limiti_reg) if ok_reg else 0
    st.markdown(
        f"{'✅' if ok_reg else '❌'} **Regolamento** - "
        f"{'**' + str(n_lim) + ' limiti**' if ok_reg else '_non caricato (solo check 474)_'}"
    )

st.divider()

if st.session_state.df_ship is not None:
    df_all = st.session_state.df_ship.copy()

    # -- Filtri gerarchici ----------------------------------------------------
    st.markdown("### Seleziona fondo")

    FILTRI = [
        ("tipo_area",                 "Area valutazione"),
        ("denominazione_impresa",     "Compagnia"),
        ("denominazione_portafoglio", "Portafoglio"),
        ("denominazione_fondo",       "Fondo (SAG)"),
    ]

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    filter_cols = [col_f1, col_f2, col_f3, col_f4]
    df_work = df_all.copy()
    selezioni = {}

    for i, (col_name, label) in enumerate(FILTRI):
        if col_name not in df_work.columns:
            continue
        valori = sorted(df_work[col_name].dropna().astype(str).unique().tolist())
        if not valori:
            continue
        sel = filter_cols[i].selectbox(label, ["(tutti)"] + valori,
                                       key=f"f_{col_name}")
        selezioni[col_name] = sel
        if sel != "(tutti)":
            df_work = df_work[df_work[col_name].astype(str) == sel]

    df_sel = df_work.reset_index(drop=True)

    # KPI
    col_val_kpi = "valore_bilancio" if "valore_bilancio" in df_sel.columns else None
    excl_kpi = df_sel.get("escluso_calcolo", pd.Series(False, index=df_sel.index))
    tot_kpi = df_sel.loc[~excl_kpi, col_val_kpi].sum() if col_val_kpi else 0

    kc1, kc2, kc3, kc4 = st.columns(4)
    kc1.metric("Totale fondo (EUR)", f"€ {tot_kpi:,.0f}")
    kc2.metric("Posizioni", f"{len(df_sel):,}")
    kc3.metric("Emittenti",
               str(df_sel["denominazione_emittente"].nunique())
               if "denominazione_emittente" in df_sel.columns else "-")
    kc4.metric("Gruppi emittente",
               str(df_sel["gruppo_emittente"].nunique())
               if "gruppo_emittente" in df_sel.columns else "-")

    st.divider()

    # Nome fondo per output
    nome_fondo = (selezioni.get("denominazione_fondo", "")
                  or selezioni.get("denominazione_portafoglio", "")
                  or "Fondo")
    if nome_fondo in ("(tutti)", ""):
        nome_fondo = "Fondo"

    # -- Basi di calcolo: selettore fondo del rendiconto + override manuale ---
    st.markdown("### Basi di calcolo")

    rend = st.session_state.rendiconto or {}

    # Inizializza i campi manuali una sola volta
    if "man_tot" not in st.session_state:
        st.session_state.man_tot = float(tot_kpi or 0.0)
    if "man_nav" not in st.session_state:
        st.session_state.man_nav = 0.0

    info_rend = None
    if rend:
        nomi_rend = list(rend.keys())

        # Default intelligente: match automatico col nome del fondo SHIP
        auto = match_fondo(nome_fondo, rend)
        default_idx = (nomi_rend.index(auto["nome_fondo"])
                       if auto and auto["nome_fondo"] in nomi_rend else 0)

        st.markdown("**Fondo del rendiconto** *(fornisce Totale attività e NAV)*")
        fondo_rend_sel = st.selectbox(
            "Seleziona il fondo del rendiconto a cui riferire le basi di calcolo:",
            nomi_rend,
            index=default_idx,
            key="sel_fondo_rend",
        )
        info_rend = rend.get(fondo_rend_sel)

        # Al cambio di fondo, aggiorna automaticamente Totale attività e NAV
        if st.session_state.get("_last_fondo_rend") != fondo_rend_sel:
            st.session_state._last_fondo_rend = fondo_rend_sel
            st.session_state.man_tot = float(info_rend.get("totale_attivita") or 0.0)
            st.session_state.man_nav = float(info_rend.get("nav") or 0.0)
            st.rerun()

        st.caption(
            f"Fondo **{info_rend['nome_fondo']}** ({info_rend['data']}) - "
            f"Totale attività € {info_rend['totale_attivita']:,.0f} · "
            f"NAV € {(info_rend.get('nav') or 0):,.0f}. "
            f"Puoi comunque sovrascrivere i valori qui sotto."
        )
    else:
        st.caption(
            "Nessun rendiconto caricato: inserisci manualmente Totale attività e NAV, "
            "oppure lascia 0 per usare il totale SHIP come base."
        )

    bcol1, bcol2 = st.columns(2)
    man_tot = bcol1.number_input(
        "Totale attività (EUR) — base limiti '% del totale attività'",
        min_value=0.0, step=1000.0, format="%.2f", key="man_tot",
    )
    man_nav = bcol2.number_input(
        "NAV / valore complessivo netto (EUR) — base limiti '% del fondo'",
        min_value=0.0, step=1000.0, format="%.2f", key="man_nav",
    )

    basi = Basi(
        totale_attivita=man_tot if man_tot > 0 else None,
        nav=man_nav if man_nav > 0 else None,
    )

    info_basi = [
        (f"Totale attività: € {man_tot:,.0f}" if man_tot > 0
         else "Totale attività: _fallback totale SHIP_"),
        (f"NAV: € {man_nav:,.0f}" if man_nav > 0
         else "NAV: _fallback totale SHIP_"),
    ]
    st.caption(" · ".join(info_basi))

    st.session_state.basi = basi

    # -- Limiti regolamento: applicati tutti ----------------------------------
    limiti_tutti = st.session_state.limiti_reg or []
    if limiti_tutti:
        st.caption(
            f"Regolamento: verranno applicati **tutti** i {len(limiti_tutti)} limiti estratti."
        )

    # -- Esegui check ---------------------------------------------------------
    st.markdown("### Esegui verifica")

    if len(df_sel) == 0:
        st.warning("Nessuna posizione nel perimetro selezionato.")
    else:
        if st.button("ESEGUI VERIFICA", type="primary", use_container_width=False):
            with st.spinner("Calcolo check 474 e regolamento…"):
                try:
                    limiti_r = st.session_state.limiti_reg or []

                    info_f = st.session_state.info_fondo or {}
                    basi = st.session_state.basi or Basi()

                    results_474 = esegui_tutti_check(
                        df_sel,
                        limiti_regolamento=None,
                        limite_non_quotati=limite_nq,
                        tipo_fondo=tipo_fondo,
                        basi=basi,
                    )

                    results_reg = check_regolamento(df_sel, limiti_r, basi) if limiti_r else []

                    st.session_state.results_474 = results_474
                    st.session_state.results_reg = results_reg
                    st.session_state.nome_fondo = nome_fondo

                    excel_b = genera_excel(
                        df_portafoglio=df_sel,
                        results_474=results_474,
                        results_reg=results_reg,
                        limiti_regolamento=limiti_r,
                        info_fondo=info_f,
                        nome_fondo=nome_fondo,
                    )
                    st.session_state.excel_bytes = excel_b
                    st.success("Verifica completata!")
                except Exception as e:
                    st.error(f"Errore: {e}")
                    st.exception(e)

    # -- Risultati ------------------------------------------------------------
    if st.session_state.results_474:
        results_474: list[CheckResult] = st.session_state.results_474
        results_reg: list[CheckResult] = st.session_state.results_reg or []

        def _esiti_count(rs):
            ok = sum(1 for r in rs if r.esito == "OK")
            err = sum(1 for r in rs if "SFORA" in r.esito)
            warn = sum(1 for r in rs if "MINIMO" in r.esito or "AVVISO" in r.esito)
            nr = sum(1 for r in rs if r.esito == "NON RILEVABILE")
            return ok, err, warn, nr

        ok4, e4, w4, nr4 = _esiti_count(results_474)
        okr, er, wr, nrr = _esiti_count(results_reg)

        st.markdown("#### Sintesi check Circolare 474/D")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("OK", ok4)
        sc2.metric("Sforamenti", e4)
        sc3.metric("Sotto minimo", w4)
        sc4.metric("Non rilevabile", nr4)

        def _color_esito(val):
            if "SFORA" in str(val):
                return "background-color:#FFC7CE;color:#9C0006;font-weight:bold"
            if "MINIMO" in str(val):
                return "background-color:#FFEB9C;color:#7D6608;font-weight:bold"
            if val == "OK":
                return "background-color:#C6EFCE;color:#276221;font-weight:bold"
            return "background-color:#D9D9D9;color:#595959"

        rows_474 = []
        for r in results_474:
            rows_474.append({
                "Check": r.check_id,
                "Descrizione": r.descrizione,
                "Limite MAX %": r.limite_max_pct,
                "Valore %": r.valore_effettivo_pct,
                "Base": BASE_LABEL.get(r.base_calcolo, r.base_calcolo),
                "Esito": r.esito,
                "Scost. pp": r.scostamento_pp,
                "Dettaglio": r.dettaglio[:80] + "…" if len(r.dettaglio) > 80 else r.dettaglio,
            })

        df_show = pd.DataFrame(rows_474)
        st.dataframe(
            df_show.style.map(_color_esito, subset=["Esito"]),
            use_container_width=True, height=420,
        )

        if results_reg:
            st.markdown("#### Sintesi check Regolamento fondo")
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("OK", okr)
            rc2.metric("Sforamenti", er)
            rc3.metric("Sotto minimo", wr)
            rc4.metric("Non rilevabile", nrr)

            rows_reg = []
            for r in results_reg:
                rows_reg.append({
                    "Descrizione": r.descrizione,
                    "Art./Par.": r.articolo,
                    "Limite MAX %": r.limite_max_pct,
                    "Limite MIN %": r.limite_min_pct,
                    "Valore %": r.valore_effettivo_pct,
                    "Base": BASE_LABEL.get(r.base_calcolo, r.base_calcolo),
                    "Esito": r.esito,
                })
            df_reg_show = pd.DataFrame(rows_reg)
            st.dataframe(
                df_reg_show.style.map(_color_esito, subset=["Esito"]),
                use_container_width=True, height=300,
            )

    # -- Download Excel -------------------------------------------------------
    if st.session_state.excel_bytes:
        st.divider()
        fname = f"Verifica_474_{st.session_state.nome_fondo.replace(' ', '_')}.xlsx"
        st.download_button(
            label="⬇ Scarica Excel verifica",
            data=st.session_state.excel_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=False,
        )
        st.markdown("**Sheet inclusi nell'Excel:**")
        sheets_info = [
            ("Verifica_474", "Check Circolare 474/D - semaforo colorato"),
            ("Verifica_Regolamento", "Check regolamento fondo - semaforo colorato"),
            ("Dettaglio_Emittenti", "Concentrazione per singolo emittente (con soglia colore)"),
            ("Dettaglio_Gruppi", "Concentrazione per gruppo emittente"),
            ("DB_Grezzo", "Portafoglio SHIP filtrato"),
            ("Limiti_Regolamento_Raw", "Limiti estratti dal regolamento"),
            ("Legenda", "Legenda colori e note metodologiche"),
        ]
        for sheet, desc in sheets_info:
            st.markdown(f"- **{sheet}** — {desc}")

else:
    st.info("Carica il portafoglio del fondo dalla sidebar per iniziare.")

st.divider()
st.caption("Verifica Limiti UL - Circolare ISVAP 474/D - v2.2")

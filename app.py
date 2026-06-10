import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pdf_parser import extract_text_from_pdf
from core.claude_extractor import (
    estrai_limiti_reg38,
    estrai_limiti_regolamento,
    estrai_info_gestione,
)
from core.ship_parser import load_ship, get_gestioni, filter_by_gestione
from core.analisi import (
    calcola_per_categoria,
    calcola_per_emittente,
    calcola_per_paese,
    calcola_per_valuta,
    verifica_limiti,
    calcola_totale,
)
from core.excel_writer import genera_excel

# Page config
st.set_page_config(
    page_title="Analisi Limiti Gestioni",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS custom
st.markdown("""
<style>
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1F3864;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #5A5A5A;
        margin-bottom: 1.5rem;
    }
    div[data-testid="stDownloadButton"] button {
        background-color: #1F3864;
        color: white;
        font-weight: 600;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        width: 100%;
    }
    div[data-testid="stDownloadButton"] button:hover {
        background-color: #2E75B6;
    }
    .filter-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #5A5A5A;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.2rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-title">Analisi Limiti Gestioni & Fondi</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Verifica limiti di investimento - Reg. IVASS n.38 + Regolamento Gestione</div>', unsafe_allow_html=True)

# Session state init
for key in ["limiti_reg38", "limiti_regolamento", "info_gestione",
            "df_ship", "gestioni_list", "testo_reg38", "testo_regolamento"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("Caricamento File")
    st.divider()

    # Step 1: PDF Regolamento Gestione
    st.markdown("**Regolamento della Gestione / Fondo**")
    pdf_regolamento = st.file_uploader(
        "Carica PDF regolamento gestione",
        type=["pdf"],
        key="upload_regolamento",
        label_visibility="collapsed",
    )
    if pdf_regolamento:
        if st.button("Estrai limiti regolamento", use_container_width=True):
            with st.spinner("Lettura PDF e analisi..."):
                try:
                    testo = extract_text_from_pdf(pdf_regolamento.read())
                    st.session_state.testo_regolamento = testo
                    st.session_state.limiti_regolamento = estrai_limiti_regolamento(testo)
                    st.session_state.info_gestione = estrai_info_gestione(testo)
                    n = len(st.session_state.limiti_regolamento)
                    st.success(f"Estratti {n} limiti dal regolamento")
                    nome = st.session_state.info_gestione.get("nome_gestione", "-")
                    st.info(f"Gestione: **{nome}**")
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.divider()

    # Step 2: PDF Normativa IVASS
    st.markdown("**Normativa IVASS sugli investimenti**")
    st.caption("Reg. n.24/2016, Reg. n.30/2016, Reg. n.38/2011 o altro")
    pdf_reg38 = st.file_uploader(
        "Carica PDF normativa IVASS",
        type=["pdf"],
        key="upload_reg38",
        label_visibility="collapsed",
    )
    if pdf_reg38:
        if st.button("Estrai limiti normativi", use_container_width=True):
            with st.spinner("Analisi normativa IVASS con Claude AI..."):
                try:
                    testo = extract_text_from_pdf(pdf_reg38.read())
                    st.session_state.testo_reg38 = testo
                    st.session_state.limiti_reg38 = estrai_limiti_reg38(testo)
                    n = len(st.session_state.limiti_reg38)
                    if n == 0:
                        st.warning("Nessun limite quantitativo trovato. Prova con il Reg. IVASS n.24/2016.")
                    else:
                        st.success(f"Estratti {n} limiti normativi")
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.divider()

    # Step 3: Portafoglio
    st.markdown("**Portafoglio**")
    ship_file = st.file_uploader(
        "Carica file (.xlsx)",
        type=["xlsx", "xls"],
        key="upload_ship",
        label_visibility="collapsed",
    )
    if ship_file:
        if st.button("Carica portafoglio", use_container_width=True):
            with st.spinner("Parsing db..."):
                try:
                    df = load_ship(ship_file.read())
                    st.session_state.df_ship = df
                    st.session_state.gestioni_list = get_gestioni(df)
                    st.success(f"{len(df):,} posizioni caricate")
                    st.info(f"{len(st.session_state.gestioni_list)} gestioni trovate")
                except Exception as e:
                    st.error(f"Errore parsing db: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

# Stato caricamento
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    ok_reg = st.session_state.limiti_regolamento is not None
    st.markdown(f"{'OK' if ok_reg else 'KO'} Regolamento gestione - "
                f"{'**' + str(len(st.session_state.limiti_regolamento)) + ' limiti**' if ok_reg else '_non caricato_'}")
with col_s2:
    ok_38 = st.session_state.limiti_reg38 is not None
    st.markdown(f"{'OK' if ok_38 else 'KO'} Reg. IVASS - "
                f"{'**' + str(len(st.session_state.limiti_reg38)) + ' limiti**' if ok_38 else '_non caricato_'}")
with col_s3:
    ok_ship = st.session_state.df_ship is not None
    n_pos = len(st.session_state.df_ship) if ok_ship else 0
    st.markdown(f"{'OK' if ok_ship else 'KO'} Portafoglio - "
                f"{'**' + str(n_pos) + ' posizioni**' if ok_ship else '_non caricato_'}")

st.divider()

# ── Filtri gerarchici + selezione gestione ────────────────────────────────────
if st.session_state.df_ship is not None:

    st.markdown("### Filtri portafoglio")

    df_work = st.session_state.df_ship.copy()

    # Definizione filtri in ordine gerarchico
    # (col_interna, label_ui)
    FILTRI = [
        ("tipo_gestione",             "Valuation Area"),
        ("denominazione_impresa",     "Compagnia"),
        ("denominazione_portafoglio", "Portfolio"),
        ("denominazione_gestione",    "Gestione / Sec. Account Group"),
    ]

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    filter_ui = [col_f1, col_f2, col_f3, col_f4]

    selezioni = {}
    for i, (col_name, label) in enumerate(FILTRI):
        if col_name not in df_work.columns:
            # colonna assente nel file caricato → skip silenzioso
            continue
        valori = sorted(df_work[col_name].dropna().astype(str).unique().tolist())
        if not valori:
            continue
        sel = filter_ui[i].selectbox(
            label,
            options=["(tutti)"] + valori,
            key=f"filt_{col_name}",
        )
        selezioni[col_name] = sel
        if sel != "(tutti)":
            df_work = df_work[df_work[col_name].astype(str) == sel]

    df_sel = df_work.reset_index(drop=True)

    # Label riepilogativa filtri attivi
    filtri_attivi = {lbl: sel for (col, lbl), sel in
                     zip([(c, l) for c, l in FILTRI if c in selezioni],
                         [selezioni.get(c, "(tutti)") for c, l in FILTRI if c in selezioni])
                     if sel != "(tutti)"}
    if filtri_attivi:
        parti = " · ".join(f"**{k}**: {v}" for k, v in filtri_attivi.items())
        st.caption(f"Filtri attivi — {parti} — {len(df_sel):,} posizioni")
    else:
        st.caption(f"{len(df_sel):,} posizioni (nessun filtro attivo)")

    # nome gestione per il file Excel (prende Security Account Group se filtrato)
    nome_g = (selezioni.get("denominazione_gestione", "")
              if selezioni.get("denominazione_gestione", "") not in ("(tutti)", "")
              else "Portafoglio")

    st.divider()

    # KPI rapidi
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    totale = 0
    col_val = ("valore_mercato" if "valore_mercato" in df_sel.columns
               else "valore_bilancio" if "valore_bilancio" in df_sel.columns
               else None)
    if col_val:
        totale = df_sel[col_val].sum()
    n_isin  = df_sel["isin"].nunique() if "isin" in df_sel.columns else len(df_sel)
    n_emit  = df_sel["denominazione_emittente"].nunique() if "denominazione_emittente" in df_sel.columns else "-"
    n_paesi = df_sel["paese_emittente"].nunique() if "paese_emittente" in df_sel.columns else "-"

    with col_k1:
        st.metric("Valore Portafoglio (EUR)", f"€ {totale:,.0f}")
    with col_k2:
        st.metric("N. Posizioni (ISIN)", f"{n_isin:,}")
    with col_k3:
        st.metric("N. Emittenti", str(n_emit))
    with col_k4:
        st.metric("N. Paesi", str(n_paesi))

    st.divider()

    # Preview
    with st.expander("Anteprima portafoglio filtrato", expanded=False):
        st.dataframe(df_sel.head(50), use_container_width=True, height=300)

    # ── Genera Excel ──────────────────────────────────────────────────────────
    st.markdown("### Genera File di Analisi")

    can_generate = ok_ship and len(df_sel) > 0
    if not ok_reg and not ok_38:
        st.warning("Carica almeno uno tra il Regolamento Gestione e la Normativa IVASS per la verifica dei limiti.")

    if can_generate:
        if st.button("GENERA EXCEL", type="primary", use_container_width=False):
            with st.spinner("Calcolo analisi e generazione Excel..."):
                try:
                    limiti_r38 = st.session_state.limiti_reg38 or []
                    limiti_rg  = st.session_state.limiti_regolamento or []
                    info_g     = st.session_state.info_gestione or {}

                    df_cat   = calcola_per_categoria(df_sel)
                    df_emit  = calcola_per_emittente(df_sel)
                    df_paesi = calcola_per_paese(df_sel)
                    df_val   = calcola_per_valuta(df_sel)

                    df_ver_38 = verifica_limiti(df_sel, limiti_r38, []) if limiti_r38 else pd.DataFrame()
                    df_ver_rg = verifica_limiti(df_sel, [], limiti_rg)  if limiti_rg  else pd.DataFrame()

                    excel_bytes = genera_excel(
                        df_portafoglio=df_sel,
                        df_cat=df_cat,
                        df_emit=df_emit,
                        df_paesi=df_paesi,
                        df_valute=df_val,
                        df_verifica_reg38=df_ver_38,
                        df_verifica_reg=df_ver_rg,
                        limiti_reg38=limiti_r38,
                        limiti_regolamento=limiti_rg,
                        nome_gestione=nome_g,
                        info_gestione=info_g,
                    )

                    st.session_state["excel_output"] = excel_bytes
                    st.session_state["excel_nome"]   = nome_g
                    st.success("Excel generato con successo!")

                except Exception as e:
                    st.error(f"Errore generazione Excel: {e}")
                    st.exception(e)

        # Download
        if st.session_state.get("excel_output"):
            nome_file = f"Analisi_Limiti_{st.session_state['excel_nome'].replace(' ', '_')}.xlsx"
            st.download_button(
                label="Scarica Excel Analisi",
                data=st.session_state["excel_output"],
                file_name=nome_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.markdown("Sheet generati nell'Excel:")
            for sheet, desc in [
                ("Cover",                "Riepilogo metadata e filtri"),
                ("DB_Grezzo",            "Portafoglio filtrato originale"),
                ("Analisi_Categorie",    "Composizione % per categoria IVASS/CIC"),
                ("Analisi_Emittenti",    "Concentrazione per emittente"),
                ("Analisi_Paesi",        "Esposizione per paese"),
                ("Analisi_Valute",       "Esposizione per valuta"),
                ("Verifica_Reg38",       "Semaforo limiti Normativa IVASS"),
                ("Verifica_Regolamento", "Semaforo limiti Regolamento Gestione"),
                ("Limiti_Reg38_Raw",     "Limiti estratti dalla Normativa IVASS"),
                ("Limiti_Regolamento_Raw", "Limiti estratti dal Regolamento"),
            ]:
                st.markdown(f"- **{sheet}** - {desc}")

else:
    st.info("Carica i file nella sidebar per iniziare l'analisi.")

st.divider()
st.caption("Analisi Limiti Gestioni")

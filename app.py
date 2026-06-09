"""
Analisi Limiti Gestioni e Fondi Assicurativi

Flusso:
  1. Caricamento PDF Regolamento Gestione
  2. Caricamento PDF Regolamento IVASS n.38
  3. Caricamento db Excel
  4. Selezione gestione da analizzare
  5. Generazione Excel con DB grezzo + sheet di analisi
"""

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
    .step-box {
        background: #F0F4FA;
        border-left: 4px solid #2E75B6;
        padding: 0.8rem 1rem;
        border-radius: 0 6px 6px 0;
        margin-bottom: 1rem;
    }
    .kpi-card {
        background: #1F3864;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
    }
    .kpi-label {
        font-size: 0.8rem;
        opacity: 0.85;
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

# SIDEBAR - Upload & Extraction
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
            with st.spinner("Lettura PDF e analisi con Claude AI..."):
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

    # Step 2: PDF Regolamento n.38
    st.markdown("**Regolamento IVASS n.38**")
    pdf_reg38 = st.file_uploader(
        "Carica PDF Reg. n.38",
        type=["pdf"],
        key="upload_reg38",
        label_visibility="collapsed",
    )

    if pdf_reg38:
        if st.button("Estrai limiti Reg. 38", use_container_width=True):
            with st.spinner("Analisi Regolamento IVASS n.38 con Claude AI..."):
                try:
                    testo = extract_text_from_pdf(pdf_reg38.read())
                    st.session_state.testo_reg38 = testo
                    st.session_state.limiti_reg38 = estrai_limiti_reg38(testo)
                    n = len(st.session_state.limiti_reg38)
                    st.success(f"Estratti {n} limiti dal Reg. n.38")
                except Exception as e:
                    st.error(f"Errore: {e}")

    st.divider()

    # Step 3: db Excel
    st.markdown("**Portafoglio SHIP Excel**")
    ship_file = st.file_uploader(
        "Carica file SHIP (.xlsx)",
        type=["xlsx", "xls"],
        key="upload_ship",
        label_visibility="collapsed",
    )

    if ship_file:
        if st.button("Carica portafoglio", use_container_width=True):
            with st.spinner("Parsing SHIP..."):
                try:
                    df = load_ship(ship_file.read())
                    st.session_state.df_ship = df
                    st.session_state.gestioni_list = get_gestioni(df)
                    st.success(f"{len(df):,} posizioni caricate")
                    st.info(f"{len(st.session_state.gestioni_list)} gestioni trovate")
                except Exception as e:
                    st.error(f"Errore parsing SHIP: {e}")

# MAIN - Selezione gestione + Analisi
# Stato caricamento
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    ok_reg = st.session_state.limiti_regolamento is not None
    st.markdown(f"{'OK' if ok_reg else 'KO'} Regolamento gestione - "
                f"{'**' + str(len(st.session_state.limiti_regolamento)) + ' limiti**' if ok_reg else '_non caricato_'}")
with col_s2:
    ok_38 = st.session_state.limiti_reg38 is not None
    st.markdown(f"{'OK' if ok_38 else 'KO'} Reg. IVASS n.38 - "
                f"{'**' + str(len(st.session_state.limiti_reg38)) + ' limiti**' if ok_38 else '_non caricato_'}")
with col_s3:
    ok_ship = st.session_state.df_ship is not None
    n_pos = len(st.session_state.df_ship) if ok_ship else 0
    st.markdown(f"{'OK' if ok_ship else 'KO'} SHIP portafoglio - "
                f"{'**' + str(n_pos) + ' posizioni**' if ok_ship else '_non caricato_'}")

st.divider()

# Selezione gestione
if st.session_state.gestioni_list:
    st.markdown("Seleziona Gestione / Fondo")
    gestione_sel = st.selectbox(
        "Gestione da analizzare",
        options=st.session_state.gestioni_list,
        label_visibility="collapsed",
    )
    
    df_sel = filter_by_gestione(st.session_state.df_ship, gestione_sel)
    
    # KPI rapidi
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    
    totale = 0
    col_val = "valore_mercato" if "valore_mercato" in df_sel.columns else (
        "valore_bilancio" if "valore_bilancio" in df_sel.columns else None
    )
    if col_val:
        totale = df_sel[col_val].sum()
    
    n_isin = df_sel["isin"].nunique() if "isin" in df_sel.columns else len(df_sel)
    n_emit = df_sel["denominazione_emittente"].nunique() if "denominazione_emittente" in df_sel.columns else "-"
    n_paesi = df_sel["paese_emittente"].nunique() if "paese_emittente" in df_sel.columns else "-"
    
    with col_k1:
        st.metric("Valore Portafoglio", f"€ {totale:,.0f}")
    with col_k2:
        st.metric("N. Posizioni (ISIN)", f"{n_isin:,}")
    with col_k3:
        st.metric("N. Emittenti", str(n_emit))
    with col_k4:
        st.metric("N. Paesi", str(n_paesi))
    
    st.divider()
    
    # Preview portafoglio
    with st.expander("Anteprima portafoglio filtrato", expanded=False):
        st.dataframe(df_sel.head(50), use_container_width=True, height=300)
    
    # ── Genera Excel ──────────────────────────────────────────────────────────
    st.markdown("### 📥 Genera File di Analisi")
    
    can_generate = ok_ship
    if not ok_reg and not ok_38:
        st.warning("⚠️ Carica almeno uno tra il Regolamento Gestione e il Reg. IVASS n.38 per la verifica dei limiti.")
    
    if can_generate:
        if st.button("⚙️ GENERA EXCEL", type="primary", use_container_width=False):
            with st.spinner("Calcolo analisi e generazione Excel..."):
                try:
                    limiti_r38 = st.session_state.limiti_reg38 or []
                    limiti_rg = st.session_state.limiti_regolamento or []
                    info_g = st.session_state.info_gestione or {}
                    
                    df_cat = calcola_per_categoria(df_sel)
                    df_emit = calcola_per_emittente(df_sel)
                    df_paesi = calcola_per_paese(df_sel)
                    df_val = calcola_per_valuta(df_sel)
                    
                    df_ver_38 = verifica_limiti(df_sel, limiti_r38, []) if limiti_r38 else pd.DataFrame()
                    df_ver_rg = verifica_limiti(df_sel, [], limiti_rg) if limiti_rg else pd.DataFrame()
                    
                    nome_g = gestione_sel
                    
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
                    st.session_state["excel_nome"] = nome_g
                    st.success("Excel generato con successo!")
                    
                except Exception as e:
                    st.error(f"Errore generazione Excel: {e}")
                    st.exception(e)
        
        # Download button
        if st.session_state.get("excel_output"):
            nome_file = f"Analisi_Limiti_{st.session_state['excel_nome'].replace(' ', '_')}.xlsx"
            st.download_button(
                label="⬇️ Scarica Excel Analisi",
                data=st.session_state["excel_output"],
                file_name=nome_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            
            # Riepilogo sheet generati
            st.markdown("Sheet generati nell'Excel:")
            sheets_info = [
                ("Cover", "Riepilogo metadata gestione"),
                ("DB_Grezzo", "Portafoglio SHIP filtrato originale"),
                ("Analisi_Categorie", "Composizione % per categoria IVASS"),
                ("Analisi_Emittenti", "Concentrazione per emittente"),
                ("Analisi_Paesi", "Esposizione per paese"),
                ("Analisi_Valute", "Esposizione per valuta"),
                ("Verifica_Reg38", "Semaforo limiti Reg. IVASS n.38"),
                ("Verifica_Regolamento", "Semaforo limiti Regolamento Gestione"),
                ("Limiti_Reg38_Raw", "Limiti estratti da Reg. n.38"),
                ("Limiti_Regolamento_Raw", "Limiti estratti dal Regolamento"),
            ]
            for sheet, desc in sheets_info:
                st.markdown(f"- **{sheet}** - {desc}")

else:
    st.info("Carica i file nella sidebar per iniziare l'analisi.")

# Footer
st.divider()
st.caption("Analisi Limiti Gestioni")

"""
Motore di analisi: calcola i valori effettivi del portafoglio e verifica i limiti.
"""
import pandas as pd
import numpy as np


# Mapping categorie IVASS → macro-categorie per confronto con limiti Reg.38
CATEGORIA_MAP = {
    # Titoli di Stato
    "1": "Titoli di Stato UE",
    "1.1": "Titoli di Stato UE",
    "1.2": "Titoli di Stato extra-UE",
    # Obbligazioni
    "2": "Obbligazioni corporate",
    "2.1": "Obbligazioni corporate quotate",
    "2.2": "Obbligazioni corporate non quotate",
    # Azioni
    "3": "Azioni quotate",
    "3.1": "Azioni quotate",
    "3.2": "Azioni non quotate",
    # Fondi
    "4": "Fondi OICR",
    "4.1": "Fondi OICR armonizzati",
    "4.2": "Fondi alternativi FIA",
    # Immobili
    "5": "Immobili",
    # Derivati
    "6": "Derivati",
    # Liquidità
    "7": "Depositi e liquidità",
    "7.1": "Depositi bancari",
    # Prestiti
    "8": "Prestiti",
    # Altro
    "9": "Altre attività",
}

COLONNE_VALORE = ["valore_mercato", "valore_bilancio"]


def _get_valore_col(df: pd.DataFrame) -> str:
    for c in COLONNE_VALORE:
        if c in df.columns and df[c].notna().any():
            return c
    raise ValueError("Nessuna colonna valore trovata nel SHIP.")


def calcola_totale(df: pd.DataFrame) -> float:
    col = _get_valore_col(df)
    return df[col].sum()


def calcola_per_categoria(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola valore e % per categoria IVASS."""
    col_val = _get_valore_col(df)
    totale = df[col_val].sum()
    
    col_cat = None
    for c in ["categoria_ivass", "Categoria IVASS", "sottocategoria_ivass"]:
        if c in df.columns:
            col_cat = c
            break
    
    if col_cat is None:
        return pd.DataFrame()
    
    grp = df.groupby(col_cat)[col_val].sum().reset_index()
    grp.columns = ["categoria_ivass", "valore"]
    grp["pct_portafoglio"] = grp["valore"] / totale * 100
    grp = grp.sort_values("valore", ascending=False).reset_index(drop=True)
    return grp


def calcola_per_emittente(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola concentrazione per emittente."""
    col_val = _get_valore_col(df)
    totale = df[col_val].sum()
    
    col_emit = None
    for c in ["denominazione_emittente", "Denominazione emittente", "lei_emittente"]:
        if c in df.columns:
            col_emit = c
            break
    
    if col_emit is None:
        return pd.DataFrame()
    
    grp = df.groupby(col_emit)[col_val].sum().reset_index()
    grp.columns = ["emittente", "valore"]
    grp["pct_portafoglio"] = grp["valore"] / totale * 100
    grp = grp.sort_values("valore", ascending=False).reset_index(drop=True)
    return grp


def calcola_per_paese(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola concentrazione per paese emittente."""
    col_val = _get_valore_col(df)
    totale = df[col_val].sum()
    
    col_paese = None
    for c in ["paese_emittente", "Paese emittente"]:
        if c in df.columns:
            col_paese = c
            break
    
    if col_paese is None:
        return pd.DataFrame()
    
    grp = df.groupby(col_paese)[col_val].sum().reset_index()
    grp.columns = ["paese", "valore"]
    grp["pct_portafoglio"] = grp["valore"] / totale * 100
    grp = grp.sort_values("valore", ascending=False).reset_index(drop=True)
    return grp


def calcola_per_valuta(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola esposizione per valuta."""
    col_val = _get_valore_col(df)
    totale = df[col_val].sum()
    
    col_val_uta = None
    for c in ["valuta", "Valuta"]:
        if c in df.columns:
            col_val_uta = c
            break
    
    if col_val_uta is None:
        return pd.DataFrame()
    
    grp = df.groupby(col_val_uta)[col_val].sum().reset_index()
    grp.columns = ["valuta", "valore"]
    grp["pct_portafoglio"] = grp["valore"] / totale * 100
    grp = grp.sort_values("valore", ascending=False).reset_index(drop=True)
    return grp


def verifica_limiti(
    df_portafoglio: pd.DataFrame,
    limiti_reg38: list[dict],
    limiti_regolamento: list[dict],
) -> pd.DataFrame:
    """
    Confronta portafoglio con limiti estratti da Reg.38 e regolamento.
    Restituisce DataFrame con colonne: fonte, categoria_asset, articolo,
    limite_max_pct, limite_min_pct, limite_emittente_pct,
    valore_effettivo_pct, max_emittente_pct, esito, scostamento
    """
    col_val = _get_valore_col(df_portafoglio)
    totale = df_portafoglio[col_val].sum()
    
    df_cat = calcola_per_categoria(df_portafoglio)
    df_emit = calcola_per_emittente(df_portafoglio)
    
    rows = []
    
    def _check_limiti(limiti: list[dict], fonte: str):
        for lim in limiti:
            cat = lim.get("categoria_asset", "")
            
            # Cerca categoria nel portafoglio (match flessibile)
            pct_effettiva = None
            if not df_cat.empty:
                matches = df_cat[
                    df_cat["categoria_ivass"].astype(str).str.lower().str.contains(
                        cat.lower()[:20], na=False
                    )
                ]
                if not matches.empty:
                    pct_effettiva = matches["pct_portafoglio"].sum()
                else:
                    pct_effettiva = 0.0
            
            # Max concentrazione emittente nella categoria
            max_emit_pct = None
            if not df_emit.empty and pct_effettiva and pct_effettiva > 0:
                max_emit_pct = df_emit["pct_portafoglio"].max()
            
            # Verifica esito
            lim_max = lim.get("limite_max_pct")
            lim_min = lim.get("limite_min_pct")
            lim_emit = lim.get("limite_emittente_pct")
            
            esito = "✅ OK"
            scostamento = None
            
            if pct_effettiva is not None:
                if lim_max is not None and pct_effettiva > lim_max:
                    esito = "❌ SFORAMENTO MAX"
                    scostamento = pct_effettiva - lim_max
                elif lim_min is not None and pct_effettiva < lim_min:
                    esito = "⚠️ SOTTO MINIMO"
                    scostamento = pct_effettiva - lim_min
                elif lim_emit is not None and max_emit_pct is not None and max_emit_pct > lim_emit:
                    esito = "❌ SFORAMENTO EMITTENTE"
                    scostamento = max_emit_pct - lim_emit
            else:
                esito = "⬜ NON RILEVABILE"
            
            rows.append({
                "fonte": fonte,
                "categoria_asset": cat,
                "articolo": lim.get("articolo", lim.get("sezione", "")),
                "limite_max_pct": lim_max,
                "limite_min_pct": lim_min,
                "limite_emittente_pct": lim_emit,
                "valore_effettivo_pct": round(pct_effettiva, 4) if pct_effettiva is not None else None,
                "max_emittente_pct": round(max_emit_pct, 4) if max_emit_pct is not None else None,
                "esito": esito,
                "scostamento_pp": round(scostamento, 4) if scostamento is not None else None,
                "note": lim.get("note", ""),
            })
    
    _check_limiti(limiti_reg38, "Reg. IVASS n.38")
    _check_limiti(limiti_regolamento, "Regolamento Gestione")
    
    return pd.DataFrame(rows)

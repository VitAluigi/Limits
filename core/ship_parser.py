import pandas as pd
import io

# Colonne standard db attese
SHIP_COLS_MAP = {
    # Identificativi
    "Codice ABI / Codice fiscale impresa": "codice_impresa",
    "Denominazione impresa": "denominazione_impresa",
    "Codice gestione/fondo": "codice_gestione",
    "Denominazione gestione/fondo": "denominazione_gestione",
    "Tipo gestione": "tipo_gestione",
    # Titolo
    "ISIN": "isin",
    "Denominazione strumento": "denominazione_strumento",
    "Codice Bloomberg": "codice_bloomberg",
    # Classificazione
    "Categoria IVASS": "categoria_ivass",
    "Sottocategoria IVASS": "sottocategoria_ivass",
    "Classe Solvency II": "classe_solvency2",
    # Emittente / Controparte
    "Paese emittente": "paese_emittente",
    "Denominazione emittente": "denominazione_emittente",
    "Codice LEI emittente": "lei_emittente",
    "Rating": "rating",
    "Settore emittente": "settore_emittente",
    # Valori
    "Valore di bilancio": "valore_bilancio",
    "Valore di mercato": "valore_mercato",
    "Quantità": "quantita",
    "Valuta": "valuta",
    # Date
    "Data scadenza": "data_scadenza",
    "Data riferimento": "data_riferimento",
}


def load_ship(file_bytes: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    df_raw = None
    sheet_used = None
    for sheet in xls.sheet_names:
        df_try = pd.read_excel(xls, sheet_name=sheet, header=None)
        if df_try.shape[0] > 2 and df_try.shape[1] > 3:
            df_raw = df_try
            sheet_used = sheet
            break
    
    if df_raw is None:
        raise ValueError("Nessun foglio dati trovato nel file SHIP.")

    header_row = 0
    max_non_null = 0
    for i in range(min(10, len(df_raw))):
        non_null = df_raw.iloc[i].notna().sum()
        if non_null > max_non_null:
            max_non_null = non_null
            header_row = i
    
    df = pd.read_excel(xls, sheet_name=sheet_used, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for orig, norm in SHIP_COLS_MAP.items():
        for col in df.columns:
            if orig.lower() in col.lower() or col.lower() in orig.lower():
                rename[col] = norm
                break
    
    df = df.rename(columns=rename)
    df = df.dropna(how="all").reset_index(drop=True)
    for col in ["valore_bilancio", "valore_mercato", "quantita"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    return df


def get_gestioni(df: pd.DataFrame) -> list[str]:
    """Restituisce lista univoca delle gestioni/fondi nel DB."""
    col = None
    for c in ["denominazione_gestione", "codice_gestione", "Denominazione gestione/fondo"]:
        if c in df.columns:
            col = c
            break
    if col is None:
        # Fallback: cerca colonne con "gestione" nel nome
        matches = [c for c in df.columns if "gestione" in c.lower() or "fondo" in c.lower()]
        if matches:
            col = matches[0]
        else:
            return ["(tutte)"]
    
    vals = df[col].dropna().unique().tolist()
    return sorted([str(v) for v in vals if str(v).strip()])


def filter_by_gestione(df: pd.DataFrame, gestione: str) -> pd.DataFrame:
    if gestione == "(tutte)":
        return df
    for col in ["denominazione_gestione", "codice_gestione"]:
        if col in df.columns:
            mask = df[col].astype(str).str.strip() == gestione.strip()
            filtered = df[mask]
            if len(filtered) > 0:
                return filtered.reset_index(drop=True)
    return df.reset_index(drop=True)

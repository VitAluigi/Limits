import pandas as pd
import io

SHIP_COLS_MAP = {
    # Identificativi
    "Codice ABI / Codice fiscale impresa": "codice_impresa",
    "Denominazione impresa": "denominazione_impresa",
    "Codice gestione/fondo": "codice_gestione",
    "Denominazione gestione/fondo": "denominazione_gestione",
    "Tipo gestione": "tipo_gestione",
    "Company Code": "codice_impresa",
    "Company Code Name": "denominazione_impresa",
    "Portfolio": "codice_portafoglio",
    "Portfolio Name": "denominazione_portafoglio",
    "Security Account Group": "codice_gestione",
    "Security Account Group Name": "denominazione_gestione",
    "Valuation Area Name": "tipo_gestione",

    # Titolo
    "ISIN": "isin",
    "ISIN Code": "isin",
    "Denominazione strumento": "denominazione_strumento",
    "Security ID Name": "denominazione_strumento",
    "Codice Bloomberg": "codice_bloomberg",

    # Classificazione
    "Balance Sheet Category Name": "categoria_bilancio_ivass",
    "Valuation Class Name": "classificazione_ifrs9",
    "Bond Classification Name": "interest_rate_classification",

    # Emittente / Controparte
    "Paese emittente": "paese_emittente",
    "Issuer Country Name": "paese_emittente",
    "Denominazione emittente": "denominazione_emittente",
    "Issuer Name": "denominazione_emittente",
    "Codice LEI emittente": "lei_emittente",
    "Issuer": "lei_emittente",
    "Rating": "rating",
    "IFRS9 Rating": "rating",
    "Rating Issue S&P": "rating_sp",
    "Rating Issue Moody's": "rating_moodys",
    "Rating Issue Fitch": "rating_fitch",
    "Settore emittente": "settore_emittente",
    "Issuer Industry Name": "settore_emittente",
    "Issuer Type Name": "issuer_type",

    # Valori
    "Valore di bilancio": "valore_bilancio",
    "Total Book Value LC": "valore_bilancio",
    "Total Market Value LC": "valore_mercato",
    "Nominal/units": "valore_nominale",
    "Issue Currency": "valuta",
    "Position Currency": "valuta",
    "Accrued Interest LC": "rateo",
    "Exchange Rate": "cambio",

    # Rischio / Duration
    "Modified Duration": "modified_duration",
    "Mac Duration": "mac_duration",
    "Market Yield": "market_yield",
    "Interest Rate": "cedola",
    "Measurement Model": "measurement_model",
    "Stage IFRS9": "stage_ifrs9",

    # Date
    "Final Due Date": "data_scadenza",
    "Data riferimento": "data_riferimento",
    "Date": "data_riferimento",
    "Acquisition Date": "data_acquisto",
    "Issue Date": "data_emissione",

    # Sezione registro
    "Sezione": "sezione_registro",
    "Product Category Name": "categoria_prodotto",
    "Product Type Name": "tipo_prodotto",
    "GRM Holding Type Name": "holding_type",
}

_NUMERIC_COLS = [
    "valore_bilancio", "valore_mercato", "valore_mercato_totale",
    "valore_nominale", "quantita", "rateo", "cambio",
    "modified_duration", "mac_duration", "market_yield", "cedola",
]


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
    already_mapped = set()

    # Match esatto
    for orig, norm in SHIP_COLS_MAP.items():
        if orig in df.columns and norm not in already_mapped:
            rename[orig] = norm
            already_mapped.add(norm)

    for orig, norm in SHIP_COLS_MAP.items():
        if norm in already_mapped:
            continue
        for col in df.columns:
            if col in rename:
                continue
            if orig.lower() in col.lower() or col.lower() in orig.lower():
                rename[col] = norm
                already_mapped.add(norm)
                break

    df = df.rename(columns=rename)
    df = df.dropna(how="all").reset_index(drop=True)

    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def get_gestioni(df: pd.DataFrame) -> list[str]:
    """Restituisce lista univoca delle gestioni/fondi nel DB."""
    for c in ["denominazione_gestione", "codice_gestione"]:
        if c in df.columns:
            vals = df[c].dropna().unique().tolist()
            vals = sorted([str(v) for v in vals if str(v).strip()])
            if vals:
                return vals

    matches = [c for c in df.columns
               if any(k in c.lower() for k in ["gestione", "fondo", "portfolio"])]
    if matches:
        vals = df[matches[0]].dropna().unique().tolist()
        return sorted([str(v) for v in vals if str(v).strip()])

    return ["(tutte)"]


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

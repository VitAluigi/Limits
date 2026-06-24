"""
ship_parser.py
Parsing del file SHIP IVASS.
Mappa le colonne originali ai nomi interni usati dal motore di analisi.
"""

import io
import pandas as pd

# ---------------------------------------------------------------------------
# Mappa colonne SHIP → nomi interni
# ---------------------------------------------------------------------------
SHIP_COLS_MAP = {
    # Identificativi
    "Date":                                 "data_riferimento",
    "Valuation Area":                       "codice_area",
    "Valuation Area Name":                  "tipo_area",
    "Company Code":                         "codice_impresa",
    "Company Code Name":                    "denominazione_impresa",
    "Portfolio":                            "codice_portafoglio",
    "Portfolio Name":                       "denominazione_portafoglio",
    "Security Account Group":              "codice_fondo",
    "Security Account Group Name":         "denominazione_fondo",

    # Classificazione strumento
    "Security Classification Name":        "security_class",
    "Valuation Class Name":                "valuation_class",
    "Product Type Name":                   "product_type",
    "Fund Type":                           "fund_type",          # UCITS / AIF / blank
    "Long/Short Position Name":            "long_short",         # Long / Short

    # ISIN e denominazione
    "ISIN Code":                           "isin",
    "Security ID Name":                    "denominazione_strumento",

    # Valore di mercato (colonna primaria per i calcoli)
    "Total Market Value LC":               "valore_mercato",
    "Total Book Value LC":                 "valore_bilancio",

    # Quotazione
    "Indicator: Listed on Exchange":       "listed",             # X = quotato, NaN = non quotato

    # Rating (fallback chain: S&P → Fitch → Moody's → IFRS9)
    "Rating Issue S&P":                    "rating_sp",
    "Rating Issue Fitch":                  "rating_fitch",
    "Rating Issue Moody's":               "rating_moodys",
    "IFRS9 Rating":                        "rating_ifrs9",

    # Emittente / Gruppo
    "Issuer Name":                         "denominazione_emittente",
    "Issuer Country Name":                 "paese_emittente",
    "Issuer Ultimate Parent Numb Name":    "gruppo_emittente",    # 474 §2 limite gruppo 30%
    "Issuer Type Name":                    "issuer_type",
    "Issuer Industry Name":                "issuer_industry",  # settore emittente per azionario settoriale

    # Valuta
    "Issue Currency":                      "valuta",
}

# Colonne non considerate ai fini del calcolo totale portafoglio
# (derivati OTC, repo, cash collateral …)
PRODUCT_TYPES_ESCLUSI = {
    "Repurchase Agreement",
    "Interest rate swap (IRS)",
    "FX Forward",
    "Credit Default Swap (CDS)",
    "Securities  Forward",
    "Other P/L Items",
    "Repo Collateral Margin Account",
}

_NUMERIC_COLS = ["valore_mercato", "valore_bilancio"]

# Rating scala S&P con ordine crescente di qualità
RATING_ORDER_SP = [
    "AAA", "AA+", "AA", "AA-",
    "A+",  "A",   "A-",
    "BBB+","BBB", "BBB-",
    "BB+", "BB",  "BB-",
    "B+",  "B",   "B-",
    "CCC+","CCC", "CCC-",
    "CC",  "C",   "D",
]

# Mappa da notazione Moody's a equivalente S&P
MOODYS_TO_SP = {
    "Aaa":"AAA","Aa1":"AA+","Aa2":"AA","Aa3":"AA-",
    "A1":"A+","A2":"A","A3":"A-",
    "Baa1":"BBB+","Baa2":"BBB","Baa3":"BBB-",
    "Ba1":"BB+","Ba2":"BB","Ba3":"BB-",
    "B1":"B+","B2":"B","B3":"B-",
    "Caa1":"CCC+","Caa2":"CCC","Caa3":"CCC-",
    "Ca":"CC","C":"C","D":"D",
}

# Rating minimi accettabili ai sensi 474 (≥ BB)
RATING_MIN_474 = {r for r in RATING_ORDER_SP if RATING_ORDER_SP.index(r) <= RATING_ORDER_SP.index("BB")}


def _normalize_rating(r) -> str | None:
    if pd.isna(r):
        return None
    r = str(r).strip().upper()
    if r in ("NR", "N/A", "NA", "NOT RATED", ""):
        return "NR"
    for m, sp in MOODYS_TO_SP.items():
        if r == m.upper():
            return sp
    if r in [x.upper() for x in RATING_ORDER_SP]:
        idx = [x.upper() for x in RATING_ORDER_SP].index(r)
        return RATING_ORDER_SP[idx]
    return None


def load_ship(file_bytes: bytes) -> pd.DataFrame:
    """
    Carica il file SHIP da bytes, individua la riga di intestazione,
    rinomina le colonne e restituisce un DataFrame pulito.
    """
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    sheet = xls.sheet_names[0]

    df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)
    header_row = 0
    max_nn = 0
    for i in range(min(10, len(df_raw))):
        nn = df_raw.iloc[i].notna().sum()
        if nn > max_nn:
            max_nn = nn
            header_row = i

    df = pd.read_excel(xls, sheet_name=sheet, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    rename = {}
    already = set()
    for orig, norm in SHIP_COLS_MAP.items():
        if orig in df.columns and norm not in already:
            rename[orig] = norm
            already.add(norm)

    df = df.rename(columns=rename).dropna(how="all").reset_index(drop=True)

    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "listed" in df.columns:
        df["is_listed"] = df["listed"].astype(str).str.strip().str.upper() == "X"
    else:
        df["is_listed"] = True

    def _best_rating(row):
        for col in ["rating_sp", "rating_fitch", "rating_moodys", "rating_ifrs9"]:
            if col in row.index:
                r = _normalize_rating(row[col])
                if r and r != "NR":
                    return r
        return "NR"

    df["rating_norm"] = df.apply(_best_rating, axis=1)

    df["rating_below_bb"] = df["rating_norm"].apply(
        lambda r: r == "NR" or r not in RATING_MIN_474
    )

    if "product_type" in df.columns:
        df["escluso_calcolo"] = df["product_type"].isin(PRODUCT_TYPES_ESCLUSI)
    else:
        df["escluso_calcolo"] = False

    return df


def get_fondi(df: pd.DataFrame) -> list[str]:
    """Restituisce la lista dei fondi (SAG) presenti nel portafoglio."""
    for c in ["denominazione_fondo", "codice_fondo"]:
        if c in df.columns:
            vals = sorted(df[c].dropna().astype(str).unique().tolist())
            if vals:
                return vals
    return ["(tutti)"]


def filter_portafoglio(df: pd.DataFrame,
                       fondo: str | None = None,
                       portafoglio: str | None = None) -> pd.DataFrame:
    """Filtra per fondo e/o portafoglio."""
    mask = pd.Series(True, index=df.index)
    if fondo and fondo not in ("(tutti)", ""):
        for col in ["denominazione_fondo", "codice_fondo"]:
            if col in df.columns:
                mask &= df[col].astype(str).str.strip() == fondo.strip()
                break
    if portafoglio and portafoglio not in ("(tutti)", ""):
        for col in ["denominazione_portafoglio", "codice_portafoglio"]:
            if col in df.columns:
                mask &= df[col].astype(str).str.strip() == portafoglio.strip()
                break
    return df[mask].reset_index(drop=True)

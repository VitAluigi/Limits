import pandas as pd

CATEGORIA_REGOLAMENTO = {
    # Obbligazionario
    "obbligazionari": [
        # Nomi SAP reali
        "Govt bonds >1 year <10 years",
        "Govt bonds >10 years",
        "Govt bonds <1 year",
        "Ordinary bond",
        "Subordinated bond",
        "Infra Bonds",
        "Index Linked Bonds",
        "Mortgage Backed Security",
        "Asset Backed Security",
        "Collateralized Debt Obligation (CDO)",
        "Perpetual Notes",
        "Credit linked note",
        "Separated Trading of Registered Interest and Principal (STRI",
        # Nomi CIC inglese (dummy/altri sistemi)
        "Government Bonds EU",
        "Government Bonds non-EU",
        "Corporate Bonds listed",
        "Corporate Bonds unlisted",
        "Covered bond",
        "Covered Bonds",
        "Cash and deposits",   # incluso nell'obbligazionario per GESAV
        "Money market",
    ],
    # Azionario
    "azionari": [
        "Share",
        "Private Equities",
        "Real Estate Shares",
        "Equities listed",
        "Equities unlisted",
        "Equity",
    ],
    # Immobiliare
    "immobiliari": [
        "Real Estate Shares",
        "Real Estate fund",
        "Real Estate",
        "Real estate",
    ],
    # Fondi / OICR / altri strumenti finanziari
    "altri strumenti": [
        "Fixed Income fund",
        "Private equity fund",
        "Mixed fund",
        "Hedge fund",
        "Real Estate fund",
        "Equity fund",
        "Money market fund",
        "Commodity fund",
        "UCITS funds",
        "AIF",
        "UCITS",
        "Fund",
    ],
    # Liquidità / depositi
    "liquidità": [
        "Money market fund",
        "Cash and deposits",
        "Cash",
        "Deposit",
    ],
    # Prestiti / finanziamenti
    "prestiti": [
        "Loan",
        "Infra Loans",
        "Loans",
    ],
    # Derivati
    "derivati": [
        "Credit Default Swap (CDS)",
        "Interest rate swap (IRS)",
        "FX Forward",
        "OTC Currency Option Call",
        "OTC Currency Option Put",
        "Asset Swap",
        "TRS Nominal",
        "OTC Payer-Swaption (Put)",
        "Cross-curr.int.rate swap (CCS)",
        "OTC Receiver-Swaption (Call)",
        "OTC Index Option Call",
        "OTC Index Option Put",
        "Securities  Forward",
    ],
}

# Classificazioni da escludere / non considerare ai fini del calcolo limiti
# (derivati, repo, strumenti fuori bilancio, voci P&L)
NOT_ASSIGNED_PRODUCT_TYPES = {
    "Repurchase Agreement",
    "Other P/L Items",
    "Repo Collateral Margin Account",
    "Credit Default Swap (CDS)",
    "Securities  Forward",
    "FX Forward",
    "OTC Currency Option Call",
    "OTC Currency Option Put",
    "Interest rate swap (IRS)",
    "OTC Index Option Put",
    "3rd party assets - OTCs",
    "TRS Nominal",
    "OTC Payer-Swaption (Put)",
    "Cross-curr.int.rate swap (CCS)",
    "OTC Receiver-Swaption (Call)",
    "OTC Index Option Call",
    "Asset Swap",
    "SPV",
    "Asset Swap (Spanish)",
    "Deposit Swap",
    "Credit Linked Deposit",
    "Irregular Fix-to-Fix Swap",
    "Cash",
}

COLONNE_VALORE = ["valore_mercato", "valore_bilancio"]

COLS_CLASS = ["sottocategoria_ivass", "Security Classification Name",
              "CIC Classification Name", "categoria_ivass"]
COLS_PROD = ["tipo_prodotto", "Product Type Name"]


def _get_valore_col(df: pd.DataFrame) -> str:
    for c in COLONNE_VALORE:
        if c in df.columns and df[c].notna().any():
            return c
    raise ValueError("Nessuna colonna valore trovata nel SHIP.")


def _get_class_col(df: pd.DataFrame):
    for c in COLS_CLASS:
        if c in df.columns:
            return c
    return None


def _get_prod_col(df: pd.DataFrame):
    for c in COLS_PROD:
        if c in df.columns:
            return c
    return None


def _is_not_assigned(class_val: str, prod_val: str) -> bool:
    """True se la riga è un derivato/repo/cash → esclusa dal calcolo limiti."""
    if str(class_val).strip().lower() == "not assigned":
        return str(prod_val).strip() in NOT_ASSIGNED_PRODUCT_TYPES
    return False


def _match_categoria(class_val: str, prod_val: str, categoria_str: str) -> bool:
    """
    Ritorna True se (Security Classification Name, Product Type Name)
    rientrano nella macro-categoria testuale del regolamento.
    """
    cat_lower = categoria_str.lower().strip()
    class_str = str(class_val).strip()

    for kw, scn_list in CATEGORIA_REGOLAMENTO.items():
        if kw in cat_lower:
            if class_str in scn_list:
                return True

    if cat_lower in class_str.lower() or class_str.lower() in cat_lower:
        return True

    return False


def _pct_per_categoria(df: pd.DataFrame, col_val: str, col_class: str,
                       col_prod, categoria_str: str) -> float:
    """% del portafoglio che matcha la categoria testuale del regolamento."""
    totale = df[col_val].sum()
    if totale == 0:
        return 0.0

    mask = df.apply(
        lambda r: _match_categoria(
            r[col_class],
            r[col_prod] if col_prod else "",
            categoria_str
        ), axis=1
    )
    return float(df.loc[mask, col_val].sum() / totale * 100)


def calcola_totale(df: pd.DataFrame) -> float:
    return df[_get_valore_col(df)].sum()


def calcola_per_categoria(df: pd.DataFrame) -> pd.DataFrame:
    col_val = _get_valore_col(df)
    col_class = _get_class_col(df)
    totale = df[col_val].sum()

    if col_class is None:
        return pd.DataFrame()

    grp = df.groupby(col_class)[col_val].sum().reset_index()
    grp.columns = ["categoria_ivass", "valore"]
    grp["pct_portafoglio"] = grp["valore"] / totale * 100
    grp = grp.sort_values("valore", ascending=False).reset_index(drop=True)
    return grp


def calcola_per_emittente(df: pd.DataFrame) -> pd.DataFrame:
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
    return grp.sort_values("valore", ascending=False).reset_index(drop=True)


def calcola_per_paese(df: pd.DataFrame) -> pd.DataFrame:
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
    return grp.sort_values("valore", ascending=False).reset_index(drop=True)


def calcola_per_valuta(df: pd.DataFrame) -> pd.DataFrame:
    col_val = _get_valore_col(df)
    totale = df[col_val].sum()
    col_valuta = None
    for c in ["valuta", "Valuta"]:
        if c in df.columns:
            col_valuta = c
            break
    if col_valuta is None:
        return pd.DataFrame()
    grp = df.groupby(col_valuta)[col_val].sum().reset_index()
    grp.columns = ["valuta", "valore"]
    grp["pct_portafoglio"] = grp["valore"] / totale * 100
    return grp.sort_values("valore", ascending=False).reset_index(drop=True)


def verifica_limiti(
    df_portafoglio: pd.DataFrame,
    limiti_reg38: list[dict],
    limiti_regolamento: list[dict],
) -> pd.DataFrame:
    col_val = _get_valore_col(df_portafoglio)
    col_class = _get_class_col(df_portafoglio)
    col_prod = _get_prod_col(df_portafoglio)
    totale = df_portafoglio[col_val].sum()

    df_emit = calcola_per_emittente(df_portafoglio)
    rows = []

    def _check(limiti: list[dict], fonte: str):
        for lim in limiti:
            cat = lim.get("categoria_asset", "")

            if col_class is not None:
                pct_eff = _pct_per_categoria(
                    df_portafoglio, col_val, col_class, col_prod, cat
                )
                any_match = df_portafoglio[col_class].astype(str).apply(
                    lambda v: _match_categoria(v, "", cat)
                ).any()
            else:
                pct_eff   = 0.0
                any_match = False

            lim_max = lim.get("limite_max_pct")
            lim_min = lim.get("limite_min_pct")
            lim_emit = lim.get("limite_emittente_pct")

            max_emit_pct = None
            if lim_emit is not None and not df_emit.empty and pct_eff > 0:
                max_emit_pct = float(df_emit["pct_portafoglio"].max())

            # Determina esito
            if not any_match and pct_eff == 0.0:
                esito = "NON RILEVABILE"
                scostamento = None
            elif lim_max is not None and pct_eff > lim_max:
                esito = "SFORAMENTO MAX"
                scostamento = round(pct_eff - lim_max, 2)
            elif lim_min is not None and pct_eff < lim_min:
                esito = "SOTTO MINIMO"
                scostamento = round(pct_eff - lim_min, 2)
            elif (lim_emit is not None and max_emit_pct is not None
                  and max_emit_pct > lim_emit):
                esito = "SFORAMENTO EMITTENTE"
                scostamento = round(max_emit_pct - lim_emit, 2)
            else:
                esito = "OK"
                scostamento = None

            rows.append({
                "fonte": fonte,
                "categoria_asset": cat,
                "articolo": lim.get("articolo", lim.get("sezione", "")),
                "limite_max_pct": lim_max,
                "limite_min_pct": lim_min,
                "limite_emittente_pct": lim_emit,
                "valore_effettivo_pct": round(pct_eff, 2),
                "max_emittente_pct": round(max_emit_pct, 2) if max_emit_pct else None,
                "esito": esito,
                "scostamento_pp": scostamento,
                "note": lim.get("note", ""),
            })

    _check(limiti_reg38,       "Reg. IVASS")
    _check(limiti_regolamento, "Regolamento Gestione")

    return pd.DataFrame(rows)

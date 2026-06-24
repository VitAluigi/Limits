"""
analisi.py
"""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Costanti regolamentari (Sezione 3 Circolare 474/D)
# ---------------------------------------------------------------------------

OICR_CLASSES = {
    "Money market fund", "Real Estate fund", "Fixed Income fund",
    "Mixed fund", "Hedge fund", "Equity fund",
    "Private equity fund",
    "Commodity fund",
}

MONETARI_PRODUCT_TYPES = {"Cash"}
MONETARI_SECURITY_CLASSES = {"Money market fund"}

# Classi assimilate ad azionario: esenti dal check rating (Par.1 Circ. 474/D)
AZIONARIO_CLASSES = {
    "Share", "Equity fund", "Real Estate Shares", "Private Equities",
    "Private equity fund", "Hedge fund",
}

# Product type da escludere dal DENOMINATORE (derivati OTC, repo, voci P&L).
ESCLUSI_PRODUCT_TYPES = {
    "Repurchase Agreement", "Repo Collateral Margin Account",
    "Interest rate swap (IRS)", "Cross-curr.int.rate swap (CCS)",
    "Deposit Swap", "Irregular Fix-to-Fix Swap",
    "Asset Swap", "Asset Swap (Spanish)", "TRS Nominal",
    "OTC Payer-Swaption (Put)", "OTC Receiver-Swaption (Call)",
    "FX Forward", "OTC Currency Option Call", "OTC Currency Option Put",
    "Credit Default Swap (CDS)",
    "OTC Index Option Put", "OTC Index Option Call",
    "3rd party assets - OTCs", "Securities  Forward",
    "Other P/L Items",
}

RATING_ORDER_SP = [
    "AAA","AA+","AA","AA-","A+","A","A-",
    "BBB+","BBB","BBB-","BB+","BB","BB-",
    "B+","B","B-","CCC+","CCC","CCC-","CC","C","D",
]
RATING_MIN_474 = set(RATING_ORDER_SP[:RATING_ORDER_SP.index("BB") + 1])

# ---------------------------------------------------------------------------
# Mappa settore → keywords su Issuer Industry Name (per azionario settoriale)
# ---------------------------------------------------------------------------
SECTOR_INDUSTRY_MAP: dict[str, list[str]] = {
    "tecnolog": [
        "computer", "software", "semiconductor", "electronic component",
        "electronic measur", "data processing", "networking",
        "internet content", "internet connect", "internet gambling",
        "e-commerce", "e-service", "web portal", "telecom services",
        "telephone - integrated", "cellular telecommun",
        "sector fund-technology", "multi-media", "automation/robotics",
        "computer data security", "applications software",
        "enterprise software", "optical supplies", "power conv/power",
        "internet & telecom",
    ],
    "sanitari": [
        "medical product", "medical instrument", "medical - drug",
        "medical - hmo", "medical - wholesale", "medical - outpatient",
        "medical labs", "drug delivery", "dialysis",
        "health & biotech", "diagnostic equipment",
    ],
    "farmaceut": [
        "medical - drug", "drug delivery", "pharmaceutical",
        "medical labs & test",
    ],
    "finanzi": [
        "bank", " finance", "finance-", "financial services",
        "diversified banking", "building societ", "cooperative bank",
        "investment management", "fiduciary", "venture capital",
        "life/health insur", "multi-line insur", "property/casualty",
        "insurance broker", "diversified financial",
    ],
    "assicurat": [
        "insurance", "life/health insur", "multi-line insur",
        "property/casualty", "insurance broker",
    ],
    "energeti": [
        "oil compan", "oil refin", "gas - transport", "gas - distribut",
        "electric - generat", "electric - distribut", "electric - transmiss",
        "electric - integrat", "electric product", "energy-alt",
        "pipelines", "petrochemi", "sector fund-energy",
    ],
    "immobiliar": [
        "reit", "real estate", "sector fund-real estate",
    ],
    "industri": [
        "machinery", "aerospace", "automotive",
        "transportation - serv", "transportation - rail",
        "transportation - marin", "transportation - equip",
        "building & constr", "building product", "building - heavy",
        "industrial gases", "industrial autom",
        "diversified manufactur", "metal process",
        "chemicals-diversif", "chemicals-special",
    ],
    "consumo": [
        "food", "beverage", "retail", "consumer product",
        "textile", "apparel", "cosmetic", "soap & cleaning",
        "brewery", "restaurant",
    ],
    "emergent": [
        "emerging market-equity", "emerging market-asset",
        "country fund-china", "country fund-india",
        "country fund-russia", "country fund-japan",
        "region fund-latin", "region fund-asian",
        "asian pacific",
    ],
    "global": [
        "global equity", "international equity", "global asset alloc",
        "geo focus-equity", "geo focused-asset",
    ],
    "small cap": [
        "growth-small cap", "index fund-small cap",
        "value", "growth-large cap",
    ],
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _col(df: pd.DataFrame, *candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _totale(df: pd.DataFrame) -> float:
    col = _col(df, "valore_bilancio")
    if col is None:
        return 0.0
    if "escluso_calcolo" in df.columns:
        return float(df.loc[~df["escluso_calcolo"], col].sum())
    return float(df[col].sum())

def _pct(valore: float, totale: float) -> float:
    if totale == 0:
        return 0.0
    return round(valore / totale * 100, 4)

def _is_azionario(row: pd.Series) -> bool:
    return str(row.get("security_class", "")).strip() in AZIONARIO_CLASSES

def _esito(valore_pct: float, limite_pct: float | None,
           minimo_pct: float | None = None) -> tuple[str, float | None]:
    if limite_pct is not None and valore_pct > limite_pct:
        return "SFORAMENTO MAX", round(valore_pct - limite_pct, 4)
    if minimo_pct is not None and valore_pct < minimo_pct:
        return "SOTTO MINIMO", round(valore_pct - minimo_pct, 4)
    return "OK", None

# ---------------------------------------------------------------------------
# Dataclass risultato check
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    norma: str
    check_id: str
    descrizione: str
    limite_max_pct: float | None
    limite_min_pct: float | None
    valore_effettivo_pct: float
    esito: str
    scostamento_pp: float | None
    dettaglio: str = ""
    articolo: str = ""

# ---------------------------------------------------------------------------
# CHECK 1 - Vendite allo scoperto
# ---------------------------------------------------------------------------

def check_short_selling(df: pd.DataFrame) -> CheckResult:
    col_pos = _col(df, "Long/Short Position")
    col_val = _col(df, "valore_bilancio")
    tot = _totale(df)

    if col_pos is None or col_val is None or tot == 0:
        return CheckResult(
            "Circ. 474/D Par.2", "474_SHORT",
            "Divieto vendite allo scoperto", 0.0, None,
            0.0, "OK", None,
            "Colonna Long/Short o valore non presente nel SHIP",
            "Par.2 Circ. 474/D",
        )

    short_val = df.loc[df[col_pos].astype(str).str.upper() == "S", col_val].sum()
    short_pct = _pct(short_val, tot)
    det = f"Posizioni short: {short_pct:.2f}% del fondo"
    esito, sc = _esito(short_pct, 0.0)
    return CheckResult(
        "Circ. 474/D Par.2", "474_SHORT",
        "Divieto vendite allo scoperto", 0.0, None,
        short_pct, esito if short_pct > 0 else "OK",
        sc if short_pct > 0 else None, det,
        "Par.2 Circ. 474/D",
    )

# ---------------------------------------------------------------------------
# CHECK 2 - Divieto commodities
# ---------------------------------------------------------------------------

def check_commodities(df: pd.DataFrame) -> CheckResult:
    COMMOD_KEYWORDS = ["commodity fund", "commodity", "commodit", "merci", "materie prime"]
    col = _col(df, "security_class")
    col_val = _col(df, "valore_bilancio")
    tot = _totale(df)

    if col is None or col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2", "474_COMMOD",
                           "Divieto investimento in merci / commodities",
                           0.0, None, 0.0, "OK", None,
                           "Colonna classificazione non presente", "Par.2 Circ. 474/D")

    mask = df[col].astype(str).str.lower().apply(
        lambda v: any(kw in v for kw in COMMOD_KEYWORDS)
    )
    commod_pct = _pct(df.loc[mask, col_val].sum(), tot)
    det = f"Strumenti commodity: {mask.sum()} posizioni ({commod_pct:.2f}%)"
    esito, sc = ("OK", None) if commod_pct == 0 else ("SFORAMENTO MAX", commod_pct)
    return CheckResult("Circ. 474/D Par.2", "474_COMMOD",
                       "Divieto investimento in merci / commodities",
                       0.0, None, commod_pct, esito, sc, det, "Par.2 Circ. 474/D")

# ---------------------------------------------------------------------------
# CHECK 3 - Strumenti monetari ≤ 20%
# ---------------------------------------------------------------------------

def check_monetari(df: pd.DataFrame) -> CheckResult:
    LIMITE = 20.0
    col_class = _col(df, "security_class")
    col_ptype = _col(df, "product_type")
    col_val   = _col(df, "valore_bilancio")
    tot = _totale(df)

    if col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2", "474_MONET",
                           "Strumenti monetari ≤ 20%", LIMITE, None,
                           0.0, "NON RILEVABILE", None, "Colonna valore non trovata")

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    mask = pd.Series(False, index=df.index)
    if col_class:
        mask |= df[col_class].isin(MONETARI_SECURITY_CLASSES)
    if col_ptype:
        mask |= df[col_ptype].isin(MONETARI_PRODUCT_TYPES)
    mask &= ~excl

    val = df.loc[mask, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, LIMITE)
    det = f"Strumenti monetari: €{val:,.0f} ({pct:.2f}% su tot. €{tot:,.0f}). Posizioni: {mask.sum()}"
    return CheckResult("Circ. 474/D Par.2", "474_MONET",
                       "Strumenti monetari ≤ 20% del fondo",
                       LIMITE, None, pct, esito, sc, det, "Par.2 Circ. 474/D")

# ---------------------------------------------------------------------------
# CHECK 4 - Titoli non quotati
# ---------------------------------------------------------------------------

def check_non_quotati(df: pd.DataFrame,
                      limite_pct: float = 10.0,
                      tipo_fondo: str = "non previdenziale") -> CheckResult:
    col_listed = _col(df, "is_listed", "listed")
    col_val    = _col(df, "valore_bilancio")
    tot = _totale(df)

    if col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2", "474_NQUOT",
                           f"Non quotati ≤ {limite_pct}%", limite_pct, None,
                           0.0, "NON RILEVABILE", None)

    if col_listed == "is_listed":
        mask_nq = ~df["is_listed"]
    elif col_listed == "listed":
        mask_nq = df["listed"].astype(str).str.strip().str.upper() != "X"
    else:
        mask_nq = pd.Series(False, index=df.index)

    if "escluso_calcolo" in df.columns:
        mask_nq &= ~df["escluso_calcolo"]

    val = df.loc[mask_nq, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)

    col_class = _col(df, "security_class")
    if col_class:
        bd = df.loc[mask_nq].groupby(col_class)[col_val].sum().sort_values(ascending=False)
        det = f"Non quotati: {pct:.2f}%. Top categorie: {'; '.join(f'{k}: €{v:,.0f}' for k,v in bd.head(5).items())}"
    else:
        det = f"Non quotati: €{val:,.0f} ({pct:.2f}%)"

    return CheckResult("Circ. 474/D Par.2", "474_NQUOT",
                       f"Titoli non quotati ≤ {limite_pct}% ({tipo_fondo})",
                       limite_pct, None, pct, esito, sc, det, "Par.2 Circ. 474/D")

# ---------------------------------------------------------------------------
# CHECK 5 - Rating minimo BB
# ---------------------------------------------------------------------------

def check_rating_minimo(df: pd.DataFrame, limite_pct: float = 5.0) -> CheckResult:
    col_val = _col(df, "valore_bilancio")
    tot = _totale(df)

    if col_val is None or tot == 0 or "rating_norm" not in df.columns:
        return CheckResult("Circ. 474/D Par.1", "474_RATING",
                           f"Rating < BB o NR ≤ {limite_pct}%", limite_pct, None,
                           0.0, "NON RILEVABILE", None, "Colonna rating non disponibile")

    col_class = _col(df, "security_class")
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))

    def _is_below(row):
        if excl.at[row.name]:
            return False
        if col_class and str(row.get("security_class","")).strip() in AZIONARIO_CLASSES:
            return False
        r = str(row.get("rating_norm", "NR")).strip()
        return r == "NR" or r not in RATING_MIN_474

    mask_below = df.apply(_is_below, axis=1)
    val = df.loc[mask_below, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)

    rating_dist = (df.loc[mask_below].groupby("rating_norm")[col_val].sum()
                   .sort_values(ascending=False))
    det = f"< BB o NR: {pct:.2f}%. Distribuzione: {'; '.join(f'{k}: €{v:,.0f}' for k,v in rating_dist.head(5).items())}"
    return CheckResult("Circ. 474/D Par.1", "474_RATING",
                       f"Titoli rating < BB o NR ≤ {limite_pct}% del fondo",
                       limite_pct, None, pct, esito, sc, det, "Par.1 Circ. 474/D")

# ---------------------------------------------------------------------------
# CHECK 6 - Concentrazione emittente ≤ 10%
# ---------------------------------------------------------------------------

def check_concentrazione_emittente(df: pd.DataFrame,
                                   limite_pct: float = 10.0) -> list[CheckResult]:
    col_emit = _col(df, "denominazione_emittente")
    col_val  = _col(df, "valore_bilancio")
    tot = _totale(df)

    if not col_emit or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2", "474_EMIT",
                            f"Concentrazione per emittente ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None,
                            "Colonna emittente o valore non trovata")]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    df_work = df.loc[~excl].copy()

    STATI_UE_KEY = ["govt bond", "government bond", "titoli di stato"]
    df_work["_esentato"] = df_work.apply(lambda r: (
        any(k in str(r.get("security_class","")).lower() for k in STATI_UE_KEY)
        or str(r.get("issuer_type","")).lower() == "government"
    ) and str(r.get("rating_norm","")).strip() == "AAA", axis=1)

    df_calc = df_work.loc[~df_work["_esentato"]]
    grp = df_calc.groupby(col_emit)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)

    max_pct = float(grp_pct.iloc[0]) if len(grp_pct) else 0.0
    emit_sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    top5 = "; ".join(f"{k}: {v:.2f}%" for k,v in grp_pct.head(5).items())
    det = f"Emittente max: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_pct:.2f}%). Top 5: {top5}"
    if len(emit_sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k,v in emit_sfora.items())}"

    results.append(CheckResult("Circ. 474/D Par.2", "474_EMIT",
                               f"Concentrazione emittente ≤ {limite_pct}% (ex Gov AAA)",
                               limite_pct, None, max_pct, esito, sc, det, "Par.2 Circ. 474/D"))

    for emit, pct_v in emit_sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2", "474_EMIT_DET",
                                   f"  ↳ Emittente: {emit}", limite_pct, None,
                                   float(pct_v), "SFORAMENTO MAX",
                                   round(float(pct_v) - limite_pct, 4),
                                   f"Valore: €{grp.get(emit,0):,.0f}", "Par.2 Circ. 474/D"))
    return results

# ---------------------------------------------------------------------------
# CHECK 7 - Concentrazione gruppo ≤ 30%
# ---------------------------------------------------------------------------

def check_concentrazione_gruppo(df: pd.DataFrame,
                                 limite_pct: float = 30.0) -> list[CheckResult]:
    col_gruppo = _col(df, "gruppo_emittente")
    col_val    = _col(df, "valore_bilancio")
    tot = _totale(df)

    if not col_gruppo or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2", "474_GRUPPO",
                            f"Concentrazione gruppo ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None,
                            "Colonna 'Issuer Ultimate Parent' non trovata")]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    grp = (df.loc[~excl].groupby(col_gruppo)[col_val].sum()
           .sort_values(ascending=False))
    grp_pct = (grp / tot * 100).round(4)

    max_pct = float(grp_pct.iloc[0]) if len(grp_pct) else 0.0
    gruppi_sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    top5 = "; ".join(f"{k}: {v:.2f}%" for k,v in grp_pct.head(5).items())
    det = f"Gruppo max: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_pct:.2f}%). Top 5: {top5}"
    if len(gruppi_sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k,v in gruppi_sfora.items())}"

    results.append(CheckResult("Circ. 474/D Par.2", "474_GRUPPO",
                               f"Concentrazione gruppo emittente ≤ {limite_pct}%",
                               limite_pct, None, max_pct, esito, sc, det,
                               "Par.2 Circ. 474/D (circ. 551 integraz.)"))

    for gruppo, pct_v in gruppi_sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2", "474_GRUPPO_DET",
                                   f"  ↳ Gruppo: {gruppo}", limite_pct, None,
                                   float(pct_v), "SFORAMENTO MAX",
                                   round(float(pct_v) - limite_pct, 4),
                                   f"Valore: €{grp.get(gruppo,0):,.0f}", "Par.2 Circ. 474/D"))
    return results

# ---------------------------------------------------------------------------
# CHECK 8 - OICR non armonizzati (AIF) ≤ 30%
# ---------------------------------------------------------------------------

def check_oicr_non_armonizzati(df: pd.DataFrame,
                                limite_pct: float = 30.0) -> CheckResult:
    col_ft  = _col(df, "fund_type")
    col_val = _col(df, "valore_bilancio")
    tot = _totale(df)

    if not col_ft or col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2", "474_AIF",
                           f"OICR non armonizzati (AIF) ≤ {limite_pct}%",
                           limite_pct, None, 0.0, "NON RILEVABILE", None,
                           "Colonna Fund Type non disponibile")

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    col_class = _col(df, "security_class")
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "AIF")
    if col_class:
        mask &= df[col_class].isin(OICR_CLASSES)

    val = df.loc[mask, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)

    if col_class and mask.any():
        bd = df.loc[mask].groupby(col_class)[col_val].sum().sort_values(ascending=False)
        det = f"AIF totale (solo OICR): {pct:.2f}%. Categorie: {'; '.join(f'{k}: €{v:,.0f}' for k,v in bd.items())}"
    else:
        det = f"AIF totale: €{val:,.0f} ({pct:.2f}%)"

    return CheckResult("Circ. 474/D Par.2", "474_AIF",
                       f"OICR non armonizzati (AIF) ≤ {limite_pct}% del fondo",
                       limite_pct, None, pct, esito, sc, det, "Par.2 Circ. 474/D")

# ---------------------------------------------------------------------------
# CHECK 9 - Singolo OICR UCITS ≤ 25%
# ---------------------------------------------------------------------------

def check_singolo_ucits(df: pd.DataFrame,
                         limite_pct: float = 25.0) -> list[CheckResult]:
    col_ft   = _col(df, "fund_type")
    col_isin = _col(df, "isin", "denominazione_strumento")
    col_val  = _col(df, "valore_bilancio")
    tot = _totale(df)

    if not col_ft or not col_isin or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2", "474_UCITS",
                            f"Singolo OICR UCITS ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None,
                            "Colonne Fund Type / ISIN non disponibili")]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    col_class = _col(df, "security_class")
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "UCITS")
    if col_class:
        mask &= df[col_class].isin(OICR_CLASSES)

    df_ucits = df.loc[mask]
    if df_ucits.empty:
        return [CheckResult("Circ. 474/D Par.2", "474_UCITS",
                            f"Singolo OICR UCITS ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "OK", None, "Nessun OICR UCITS presente")]

    grp = df_ucits.groupby(col_isin)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0])
    sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    det = f"Max singolo UCITS: {grp_pct.index[0]} ({max_pct:.2f}%)"
    if len(sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k,v in sfora.items())}"

    results.append(CheckResult("Circ. 474/D Par.2", "474_UCITS",
                               f"Singolo OICR UCITS ≤ {limite_pct}%",
                               limite_pct, None, max_pct, esito, sc, det, "Par.2 Circ. 474/D"))
    for isin, pct_v in sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2", "474_UCITS_DET",
                                   f"  ↳ UCITS: {isin}", limite_pct, None,
                                   float(pct_v), "SFORAMENTO MAX",
                                   round(float(pct_v) - limite_pct, 4),
                                   f"Valore: €{grp.get(isin,0):,.0f}", "Par.2 Circ. 474/D"))
    return results

# ---------------------------------------------------------------------------
# CHECK 10 - Singolo OICR AIF ≤ 10%
# ---------------------------------------------------------------------------

def check_singolo_aif(df: pd.DataFrame,
                       limite_pct: float = 10.0) -> list[CheckResult]:
    col_ft   = _col(df, "fund_type")
    col_isin = _col(df, "isin", "denominazione_strumento")
    col_val  = _col(df, "valore_bilancio")
    tot = _totale(df)

    if not col_ft or not col_isin or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2", "474_AIF_SING",
                            f"Singolo OICR AIF ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None)]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    col_class = _col(df, "security_class")
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "AIF")
    if col_class:
        mask &= df[col_class].isin(OICR_CLASSES)

    df_aif = df.loc[mask]
    if df_aif.empty:
        return [CheckResult("Circ. 474/D Par.2", "474_AIF_SING",
                            f"Singolo OICR AIF ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "OK", None, "Nessun OICR AIF presente")]

    grp = df_aif.groupby(col_isin)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0])
    sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    det = f"Max singolo AIF: {grp_pct.index[0]} ({max_pct:.2f}%)"
    if len(sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k,v in sfora.items())}"

    results.append(CheckResult("Circ. 474/D Par.2", "474_AIF_SING",
                               f"Singolo OICR non armonizzato (AIF) ≤ {limite_pct}%",
                               limite_pct, None, max_pct, esito, sc, det, "Par.2 Circ. 474/D"))
    for isin, pct_v in sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2", "474_AIF_SING_DET",
                                   f"  ↳ AIF: {isin}", limite_pct, None,
                                   float(pct_v), "SFORAMENTO MAX",
                                   round(float(pct_v) - limite_pct, 4),
                                   f"Valore: €{grp.get(isin,0):,.0f}", "Par.2 Circ. 474/D"))
    return results

# ---------------------------------------------------------------------------
# CHECK REGOLAMENTO - limiti estratti dal regolamento del fondo
# ---------------------------------------------------------------------------

def check_regolamento(df: pd.DataFrame,
                       limiti: list[dict]) -> list[CheckResult]:
    col_val = _col(df, "valore_bilancio")
    col_class = _col(df, "security_class")
    col_ptype = _col(df, "product_type")
    col_ind = _col(df, "issuer_industry")   # Issuer Industry Name (opzionale)
    tot = _totale(df)
    results = []

    if col_val is None or tot == 0:
        return results

    # -- MACRO_MAP ---------------------------------------------------------
    _OBB = {
        "Govt bonds <1 year", "Govt bonds >1 year <10 years", "Govt bonds >10 years",
        "Separated Trading of Registered Interest and Principal (STRI",
        "Ordinary bond", "Subordinated bond", "Perpetual Notes", "Credit linked note",
        "Infra Bonds", "Infra Loans", "Index Linked Bonds",
        "Mortgage Backed Security", "Asset Backed Security",
        "Collateralized Debt Obligation (CDO)", "Loan",
    }
    _AZ = {"Share", "Real Estate Shares", "Private Equities", "Equity fund"}

    MACRO_MAP: list[tuple[str, set[str], str | None]] = [
        # - settoriali prima (più specifiche) -
        ("azionario tecnolog", _AZ, "tecnolog"),
        ("azionario sanitari", _AZ, "sanitari"),
        ("azionario farmaceut", _AZ, "farmaceut"),
        ("azionario finanziar", _AZ, "finanzi"),
        ("azionario assicurat", _AZ, "assicurat"),
        ("azionario energeti", _AZ, "energeti"),
        ("azionario immobiliar",_AZ, "immobiliar"),
        ("azionario industri", _AZ, "industri"),
        ("azionario consumo", _AZ, "consumo"),
        ("azionario emergent", _AZ, "emergent"),
        ("azionario global", _AZ, "global"),
        # - altri strumenti -
        ("altri strumenti", {"Fixed Income fund","Private equity fund","Mixed fund",
                             "Hedge fund","Real Estate fund","Equity fund",
                             "Money market fund"}, None),
        ("obbligazionari", _OBB, None),
        ("infrastruttu", {"Infra Bonds"}, None),
        ("immobiliar", {"Real Estate fund","Real Estate Shares"}, None),
        ("flessibil", {"Mixed fund","Fixed Income fund"}, None),
        ("bilancia", {"Mixed fund"}, None),
        ("monetari", {"Money market fund"}, None),
        ("prestiti", {"Loan"}, None),
        ("liquid", set(), None),
        ("azionari", _AZ, None),
        ("fondi", {"Fixed Income fund","Mixed fund","Hedge fund",
                   "Equity fund","Real Estate fund","Money market fund"}, None),
    ]

    _INCLUDE_CASH_PT = {"liquid"}

    def _match(cat_str: str) -> tuple[set[str], bool, str | None]:
        """Restituisce (security_classes, include_cash, sector_key)."""
        cat_lower = cat_str.lower().strip()
        for macro, sc_set, sector_key in MACRO_MAP:
            if macro in cat_lower:
                return sc_set, (macro in _INCLUDE_CASH_PT), sector_key
        return {cat_str}, False, None

    excl_calc = df.get("escluso_calcolo", pd.Series(False, index=df.index))

    for lim in limiti:
        cat = lim.get("categoria_asset", "")
        lim_max = lim.get("limite_max_pct")
        lim_min = lim.get("limite_min_pct")
        lim_emit = lim.get("limite_emittente_pct")
        sezione = lim.get("sezione", lim.get("articolo", ""))

        sc_set, include_cash, sector_key = _match(cat)

        # Maschera base su security_class
        if col_class and sc_set:
            mask = df[col_class].isin(sc_set)
        else:
            mask = pd.Series(False, index=df.index)

        # Cash per categorie "liquid*"
        if include_cash and col_ptype:
            mask |= df[col_ptype].isin({"Cash"})

        # Filtro settoriale su Issuer Industry Name (solo se colonna disponibile)
        industry_note = ""
        if sector_key and col_ind:
            kws = SECTOR_INDUSTRY_MAP.get(sector_key, [])
            if kws:
                ind_mask = df[col_ind].astype(str).str.lower().apply(
                    lambda v: any(k in v for k in kws)
                )
                mask &= ind_mask
                industry_note = f" [filtro settore: {sector_key}]"
        elif sector_key and not col_ind:
            # Colonna industry assente: avvisa ma non blocca
            industry_note = " [issuer_industry non disponibile: valore approssimato]"

        # Escludi posizioni fuori denominatore
        mask &= ~excl_calc

        val = df.loc[mask, col_val].sum()
        pct = _pct(val, tot)
        any_match = mask.any()

        if not any_match and pct == 0.0:
            esito, sc = "NON RILEVABILE", None
        else:
            esito, sc = _esito(pct, lim_max, lim_min)

        det = f"Categoria '{cat}': €{val:,.0f} ({pct:.2f}% del tot. €{tot:,.0f}){industry_note}"

        results.append(CheckResult(
            norma="Regolamento fondo",
            check_id=f"REG_{cat[:20].upper().replace(' ','_')}",
            descrizione=cat,
            limite_max_pct=lim_max,
            limite_min_pct=lim_min,
            valore_effettivo_pct=pct,
            esito=esito,
            scostamento_pp=sc,
            dettaglio=det,
            articolo=sezione,
        ))

        # Check emittente per categoria (se richiesto)
        if lim_emit is not None and any_match:
            col_emit = _col(df, "denominazione_emittente")
            if col_emit:
                grp = df.loc[mask].groupby(col_emit)[col_val].sum()
                grp_pct = (grp / tot * 100).sort_values(ascending=False)
                max_emit_pct = float(grp_pct.iloc[0]) if len(grp_pct) else 0.0
                esito_e, sc_e = _esito(max_emit_pct, lim_emit)
                results.append(CheckResult(
                    norma="Regolamento fondo",
                    check_id=f"REG_EMIT_{cat[:15].upper().replace(' ','_')}",
                    descrizione=f"  ↳ Max emittente in '{cat}'",
                    limite_max_pct=lim_emit,
                    limite_min_pct=None,
                    valore_effettivo_pct=max_emit_pct,
                    esito=esito_e,
                    scostamento_pp=sc_e,
                    dettaglio=(f"Max emittente: {grp_pct.index[0] if len(grp_pct) else 'N/A'} "
                               f"({max_emit_pct:.2f}%)"),
                    articolo=sezione,
                ))

    return results

# ---------------------------------------------------------------------------
# Runner principale
# ---------------------------------------------------------------------------

def esegui_tutti_check(
    df: pd.DataFrame,
    limiti_regolamento: list[dict] | None = None,
    limite_non_quotati: float = 10.0,
    tipo_fondo: str = "non previdenziale",
) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(check_short_selling(df))
    results.append(check_commodities(df))
    results.append(check_monetari(df))
    results.append(check_non_quotati(df, limite_non_quotati, tipo_fondo))
    results.append(check_rating_minimo(df))
    results.extend(check_concentrazione_emittente(df))
    results.extend(check_concentrazione_gruppo(df))
    results.append(check_oicr_non_armonizzati(df))
    results.extend(check_singolo_ucits(df))
    results.extend(check_singolo_aif(df))
    if limiti_regolamento:
        results.extend(check_regolamento(df, limiti_regolamento))
    return results

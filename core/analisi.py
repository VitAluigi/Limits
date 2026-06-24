"""
analisi.py
Check Circolare 474/D + check regolamento, con BASE DI CALCOLO selezionabile.
"""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field

BASE_TOTALE_ATTIVITA = "totale_attivita"
BASE_NAV             = "nav"
BASE_CATEGORIA       = "categoria"
BASE_SHIP            = "ship"

BASE_LABEL = {
    BASE_TOTALE_ATTIVITA: "Totale attività (rendiconto)",
    BASE_NAV:             "NAV / valore complessivo (rendiconto)",
    BASE_CATEGORIA:       "Totale categoria",
    BASE_SHIP:            "Totale SHIP (somma posizioni)",
}


@dataclass
class Basi:
    totale_attivita: float | None = None
    nav: float | None = None

    def risolvi(self, tipo: str) -> float | None:
        if tipo == BASE_TOTALE_ATTIVITA:
            return self.totale_attivita
        if tipo == BASE_NAV:
            return self.nav
        return None


OICR_CLASSES = {
    "Money market fund", "Real Estate fund", "Fixed Income fund",
    "Mixed fund", "Hedge fund", "Equity fund",
    "Private equity fund", "Commodity fund",
}
MONETARI_PRODUCT_TYPES = {"Cash"}
MONETARI_SECURITY_CLASSES = {"Money market fund"}
AZIONARIO_CLASSES = {
    "Share", "Equity fund", "Real Estate Shares", "Private Equities",
    "Private equity fund", "Hedge fund",
}
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
# Mappatura categorie regolamento (condivisa fra check e dettaglio)
# ---------------------------------------------------------------------------
_OBB_CLASSES = {
    "Govt bonds <1 year", "Govt bonds >1 year <10 years", "Govt bonds >10 years",
    "Separated Trading of Registered Interest and Principal (STRI",
    "Ordinary bond", "Subordinated bond", "Perpetual Notes", "Credit linked note",
    "Infra Bonds", "Infra Loans", "Index Linked Bonds",
    "Mortgage Backed Security", "Asset Backed Security",
    "Collateralized Debt Obligation (CDO)", "Loan",
}
_AZ_CLASSES = {"Share", "Real Estate Shares", "Private Equities", "Equity fund"}
_MACRO_MAP: list[tuple[str, set[str], str | None]] = [
    ("azionario tecnolog", _AZ_CLASSES, "tecnolog"),
    ("azionario sanitari", _AZ_CLASSES, "sanitari"),
    ("azionario farmaceut", _AZ_CLASSES, "farmaceut"),
    ("azionario finanziar", _AZ_CLASSES, "finanzi"),
    ("azionario assicurat", _AZ_CLASSES, "assicurat"),
    ("azionario energeti", _AZ_CLASSES, "energeti"),
    ("azionario immobiliar", _AZ_CLASSES, "immobiliar"),
    ("azionario industri", _AZ_CLASSES, "industri"),
    ("azionario consumo", _AZ_CLASSES, "consumo"),
    ("azionario emergent", _AZ_CLASSES, "emergent"),
    ("azionario global", _AZ_CLASSES, "global"),
    ("altri strumenti", {"Fixed Income fund", "Private equity fund", "Mixed fund",
                         "Hedge fund", "Real Estate fund", "Equity fund",
                         "Money market fund"}, None),
    ("obbligazionari", _OBB_CLASSES, None),
    ("infrastruttu", {"Infra Bonds"}, None),
    ("immobiliar", {"Real Estate fund", "Real Estate Shares"}, None),
    ("flessibil", {"Mixed fund", "Fixed Income fund"}, None),
    ("bilancia", {"Mixed fund"}, None),
    ("monetari", {"Money market fund"}, None),
    ("prestiti", {"Loan"}, None),
    ("liquid", set(), None),
    ("azionari", _AZ_CLASSES, None),
    ("fondi", {"Fixed Income fund", "Mixed fund", "Hedge fund",
               "Equity fund", "Real Estate fund", "Money market fund"}, None),
]
_INCLUDE_CASH = {"liquid"}


def match_categoria_reg(cat_str: str) -> tuple[set[str], bool, str | None]:
    cl = str(cat_str).lower().strip()
    for macro, sc_set, sector_key in _MACRO_MAP:
        if macro in cl:
            return sc_set, (macro in _INCLUDE_CASH), sector_key
    return {cat_str}, False, None


def _mask_categoria(df, cat, col_class, col_ptype, col_ind):
    """Maschera posizioni della categoria regolamento (stessa logica del check)."""
    sc_set, include_cash, sector_key = match_categoria_reg(cat)
    if col_class and sc_set:
        mask = df[col_class].isin(sc_set)
    else:
        mask = pd.Series(False, index=df.index)
    if include_cash and col_ptype:
        mask |= df[col_ptype].isin({"Cash"})
    if sector_key and col_ind:
        kws = SECTOR_INDUSTRY_MAP.get(sector_key, [])
        if kws:
            mask &= df[col_ind].astype(str).str.lower().apply(
                lambda v: any(k in v for k in kws))
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    return mask & ~excl


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _col(df, *candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _totale(df):
    col = _col(df, "valore_bilancio")
    if col is None:
        return 0.0
    if "escluso_calcolo" in df.columns:
        return float(df.loc[~df["escluso_calcolo"], col].sum())
    return float(df[col].sum())

def _den(df, basi, tipo):
    if basi is not None:
        v = basi.risolvi(tipo)
        if v and v > 0:
            return float(v), tipo
    return _totale(df), BASE_SHIP

def _pct(valore, totale):
    if not totale:
        return 0.0
    return round(valore / totale * 100, 4)

def _esito(valore_pct, limite_pct, minimo_pct=None):
    if limite_pct is not None and valore_pct > limite_pct:
        return "SFORAMENTO MAX", round(valore_pct - limite_pct, 4)
    if minimo_pct is not None and valore_pct < minimo_pct:
        return "SOTTO MINIMO", round(valore_pct - minimo_pct, 4)
    return "OK", None


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
    base_calcolo: str = BASE_SHIP
    base_valore: float = 0.0
    dettaglio_df: object = None
    dettaglio_meta: dict = None

def _basenote(base_eff, tot):
    return f" [base: {BASE_LABEL.get(base_eff, base_eff)} = €{tot:,.0f}]"


def check_short_selling(df, basi=None):
    col_pos = _col(df, "Long/Short Position", "long_short")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_NAV)
    if col_pos is None or col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2","474_SHORT","Divieto vendite allo scoperto",0.0,None,0.0,"OK",None,"Colonna Long/Short o valore non presente nel SHIP","Par.2 Circ. 474/D",base_eff,tot)
    short_val = df.loc[df[col_pos].astype(str).str.upper().str.startswith("S"), col_val].sum()
    short_pct = _pct(short_val, tot)
    esito, sc = _esito(short_pct, 0.0)
    det = f"Posizioni short: {short_pct:.2f}% del fondo" + _basenote(base_eff, tot)
    return CheckResult("Circ. 474/D Par.2","474_SHORT","Divieto vendite allo scoperto",0.0,None,short_pct,esito if short_pct>0 else "OK",sc if short_pct>0 else None,det,"Par.2 Circ. 474/D",base_eff,tot)

def check_commodities(df, basi=None):
    KW = ["commodity fund","commodity","commodit","merci","materie prime"]
    col = _col(df, "security_class")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_NAV)
    if col is None or col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2","474_COMMOD","Divieto investimento in merci / commodities",0.0,None,0.0,"OK",None,"Colonna classificazione non presente","Par.2 Circ. 474/D",base_eff,tot)
    mask = df[col].astype(str).str.lower().apply(lambda v: any(kw in v for kw in KW))
    commod_pct = _pct(df.loc[mask, col_val].sum(), tot)
    det = f"Strumenti commodity: {int(mask.sum())} posizioni ({commod_pct:.2f}%)" + _basenote(base_eff, tot)
    esito, sc = ("OK", None) if commod_pct == 0 else ("SFORAMENTO MAX", commod_pct)
    return CheckResult("Circ. 474/D Par.2","474_COMMOD","Divieto investimento in merci / commodities",0.0,None,commod_pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot)

def check_monetari(df, basi=None):
    LIMITE = 20.0
    col_class = _col(df, "security_class")
    col_ptype = _col(df, "product_type")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_NAV)
    if col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2","474_MONET","Strumenti monetari <= 20%",LIMITE,None,0.0,"NON RILEVABILE",None,"Colonna valore non trovata","Par.2 Circ. 474/D",base_eff,tot)
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    mask = pd.Series(False, index=df.index)
    if col_class: mask |= df[col_class].isin(MONETARI_SECURITY_CLASSES)
    if col_ptype: mask |= df[col_ptype].isin(MONETARI_PRODUCT_TYPES)
    mask &= ~excl
    val = df.loc[mask, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, LIMITE)
    det = f"Strumenti monetari: €{val:,.0f} ({pct:.2f}%). Posizioni: {int(mask.sum())}" + _basenote(base_eff, tot)
    return CheckResult("Circ. 474/D Par.2","474_MONET","Strumenti monetari <= 20% del fondo",LIMITE,None,pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot)

def check_non_quotati(df, limite_pct=10.0, tipo_fondo="non previdenziale", basi=None):
    col_listed = _col(df, "is_listed", "listed")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_TOTALE_ATTIVITA)
    if col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2","474_NQUOT",f"Non quotati <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"","Par.2 Circ. 474/D",base_eff,tot)
    if col_listed == "is_listed":
        mask_nq = ~df["is_listed"]
    elif col_listed == "listed":
        mask_nq = df["listed"].astype(str).str.strip().str.upper() != "X"
    else:
        mask_nq = pd.Series(False, index=df.index)
    if "escluso_calcolo" in df.columns: mask_nq &= ~df["escluso_calcolo"]
    val = df.loc[mask_nq, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)
    col_class = _col(df, "security_class")
    if col_class:
        bd = df.loc[mask_nq].groupby(col_class)[col_val].sum().sort_values(ascending=False)
        det = f"Non quotati: {pct:.2f}%. Top categorie: " + "; ".join(f"{k}: €{v:,.0f}" for k, v in bd.head(5).items())
    else:
        det = f"Non quotati: €{val:,.0f} ({pct:.2f}%)"
    det += _basenote(base_eff, tot)
    return CheckResult("Circ. 474/D Par.2","474_NQUOT",f"Titoli non quotati <= {limite_pct}% ({tipo_fondo})",limite_pct,None,pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot)

def check_rating_minimo(df, limite_pct=5.0, basi=None):
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_NAV)
    if col_val is None or tot == 0 or "rating_norm" not in df.columns:
        return CheckResult("Circ. 474/D Par.1","474_RATING",f"Rating < BB o NR <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"Colonna rating non disponibile","Par.1 Circ. 474/D",base_eff,tot)
    col_class = _col(df, "security_class")
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    def _is_below(row):
        if excl.at[row.name]: return False
        if col_class and str(row.get("security_class","")).strip() in AZIONARIO_CLASSES: return False
        r = str(row.get("rating_norm","NR")).strip()
        return r == "NR" or r not in RATING_MIN_474
    mask_below = df.apply(_is_below, axis=1)
    val = df.loc[mask_below, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)
    rating_dist = df.loc[mask_below].groupby("rating_norm")[col_val].sum().sort_values(ascending=False)
    det = f"< BB o NR: {pct:.2f}%. Distribuzione: " + "; ".join(f"{k}: €{v:,.0f}" for k, v in rating_dist.head(5).items()) + _basenote(base_eff, tot)
    return CheckResult("Circ. 474/D Par.1","474_RATING",f"Titoli rating < BB o NR <= {limite_pct}% del fondo",limite_pct,None,pct,esito,sc,det,"Par.1 Circ. 474/D",base_eff,tot)

def check_concentrazione_emittente(df, limite_pct=10.0, basi=None):
    col_emit = _col(df, "denominazione_emittente")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_TOTALE_ATTIVITA)
    if not col_emit or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2","474_EMIT",f"Concentrazione per emittente <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"Colonna emittente o valore non trovata","Par.2 Circ. 474/D",base_eff,tot)]
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    df_work = df.loc[~excl].copy()
    STATI = ["govt bond","government bond","titoli di stato"]
    df_work["_esentato"] = df_work.apply(lambda r: (any(k in str(r.get("security_class","")).lower() for k in STATI) or str(r.get("issuer_type","")).lower()=="government") and str(r.get("rating_norm","")).strip()=="AAA", axis=1)
    df_calc = df_work.loc[~df_work["_esentato"]]
    grp = df_calc.groupby(col_emit)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0]) if len(grp_pct) else 0.0
    emit_sfora = grp_pct[grp_pct > limite_pct]
    results = []
    esito, sc = _esito(max_pct, limite_pct)
    top5 = "; ".join(f"{k}: {v:.2f}%" for k, v in grp_pct.head(5).items())
    det = f"Emittente max: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_pct:.2f}%). Top 5: {top5}"
    if len(emit_sfora): det += " | SFORA: " + ", ".join(f"{k} ({v:.2f}%)" for k, v in emit_sfora.items())
    det += _basenote(base_eff, tot)
    results.append(CheckResult("Circ. 474/D Par.2","474_EMIT",f"Concentrazione emittente <= {limite_pct}% (ex Gov AAA)",limite_pct,None,max_pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot))
    for emit, pct_v in emit_sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2","474_EMIT_DET",f"  -> Emittente: {emit}",limite_pct,None,float(pct_v),"SFORAMENTO MAX",round(float(pct_v)-limite_pct,4),f"Valore: €{grp.get(emit,0):,.0f}","Par.2 Circ. 474/D",base_eff,tot))
    return results

def check_concentrazione_gruppo(df, limite_pct=30.0, basi=None):
    col_gruppo = _col(df, "gruppo_emittente")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_TOTALE_ATTIVITA)
    if not col_gruppo or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2","474_GRUPPO",f"Concentrazione gruppo <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"Colonna 'Issuer Ultimate Parent' non trovata","Par.2 Circ. 474/D",base_eff,tot)]
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    grp = df.loc[~excl].groupby(col_gruppo)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0]) if len(grp_pct) else 0.0
    gruppi_sfora = grp_pct[grp_pct > limite_pct]
    results = []
    esito, sc = _esito(max_pct, limite_pct)
    top5 = "; ".join(f"{k}: {v:.2f}%" for k, v in grp_pct.head(5).items())
    det = f"Gruppo max: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_pct:.2f}%). Top 5: {top5}"
    if len(gruppi_sfora): det += " | SFORA: " + ", ".join(f"{k} ({v:.2f}%)" for k, v in gruppi_sfora.items())
    det += _basenote(base_eff, tot)
    results.append(CheckResult("Circ. 474/D Par.2","474_GRUPPO",f"Concentrazione gruppo emittente <= {limite_pct}%",limite_pct,None,max_pct,esito,sc,det,"Par.2 Circ. 474/D (circ. 551 integraz.)",base_eff,tot))
    for gruppo, pct_v in gruppi_sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2","474_GRUPPO_DET",f"  -> Gruppo: {gruppo}",limite_pct,None,float(pct_v),"SFORAMENTO MAX",round(float(pct_v)-limite_pct,4),f"Valore: €{grp.get(gruppo,0):,.0f}","Par.2 Circ. 474/D",base_eff,tot))
    return results

def check_oicr_non_armonizzati(df, limite_pct=30.0, basi=None):
    col_ft = _col(df, "fund_type")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_TOTALE_ATTIVITA)
    if not col_ft or col_val is None or tot == 0:
        return CheckResult("Circ. 474/D Par.2","474_AIF",f"OICR non armonizzati (AIF) <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"Colonna Fund Type non disponibile","Par.2 Circ. 474/D",base_eff,tot)
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    col_class = _col(df, "security_class")
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "AIF")
    if col_class: mask &= df[col_class].isin(OICR_CLASSES)
    val = df.loc[mask, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)
    if col_class and mask.any():
        bd = df.loc[mask].groupby(col_class)[col_val].sum().sort_values(ascending=False)
        det = f"AIF totale (solo OICR): {pct:.2f}%. Categorie: " + "; ".join(f"{k}: €{v:,.0f}" for k, v in bd.items())
    else:
        det = f"AIF totale: €{val:,.0f} ({pct:.2f}%)"
    det += _basenote(base_eff, tot)
    return CheckResult("Circ. 474/D Par.2","474_AIF",f"OICR non armonizzati (AIF) <= {limite_pct}% del fondo",limite_pct,None,pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot)

def check_singolo_ucits(df, limite_pct=25.0, basi=None):
    col_ft = _col(df, "fund_type")
    col_isin = _col(df, "isin", "denominazione_strumento")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_TOTALE_ATTIVITA)
    if not col_ft or not col_isin or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2","474_UCITS",f"Singolo OICR UCITS <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"Colonne Fund Type / ISIN non disponibili","Par.2 Circ. 474/D",base_eff,tot)]
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    col_class = _col(df, "security_class")
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "UCITS")
    if col_class: mask &= df[col_class].isin(OICR_CLASSES)
    df_ucits = df.loc[mask]
    if df_ucits.empty:
        return [CheckResult("Circ. 474/D Par.2","474_UCITS",f"Singolo OICR UCITS <= {limite_pct}%",limite_pct,None,0.0,"OK",None,"Nessun OICR UCITS presente","Par.2 Circ. 474/D",base_eff,tot)]
    grp = df_ucits.groupby(col_isin)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0])
    sfora = grp_pct[grp_pct > limite_pct]
    results = []
    esito, sc = _esito(max_pct, limite_pct)
    det = f"Max singolo UCITS: {grp_pct.index[0]} ({max_pct:.2f}%)"
    if len(sfora): det += " | SFORA: " + ", ".join(f"{k} ({v:.2f}%)" for k, v in sfora.items())
    det += _basenote(base_eff, tot)
    results.append(CheckResult("Circ. 474/D Par.2","474_UCITS",f"Singolo OICR UCITS <= {limite_pct}%",limite_pct,None,max_pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot))
    for isin, pct_v in sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2","474_UCITS_DET",f"  -> UCITS: {isin}",limite_pct,None,float(pct_v),"SFORAMENTO MAX",round(float(pct_v)-limite_pct,4),f"Valore: €{grp.get(isin,0):,.0f}","Par.2 Circ. 474/D",base_eff,tot))
    return results

def check_singolo_aif(df, limite_pct=10.0, basi=None):
    col_ft = _col(df, "fund_type")
    col_isin = _col(df, "isin", "denominazione_strumento")
    col_val = _col(df, "valore_bilancio")
    tot, base_eff = _den(df, basi, BASE_TOTALE_ATTIVITA)
    if not col_ft or not col_isin or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D Par.2","474_AIF_SING",f"Singolo OICR AIF <= {limite_pct}%",limite_pct,None,0.0,"NON RILEVABILE",None,"","Par.2 Circ. 474/D",base_eff,tot)]
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    col_class = _col(df, "security_class")
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "AIF")
    if col_class: mask &= df[col_class].isin(OICR_CLASSES)
    df_aif = df.loc[mask]
    if df_aif.empty:
        return [CheckResult("Circ. 474/D Par.2","474_AIF_SING",f"Singolo OICR AIF <= {limite_pct}%",limite_pct,None,0.0,"OK",None,"Nessun OICR AIF presente","Par.2 Circ. 474/D",base_eff,tot)]
    grp = df_aif.groupby(col_isin)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0])
    sfora = grp_pct[grp_pct > limite_pct]
    results = []
    esito, sc = _esito(max_pct, limite_pct)
    det = f"Max singolo AIF: {grp_pct.index[0]} ({max_pct:.2f}%)"
    if len(sfora): det += " | SFORA: " + ", ".join(f"{k} ({v:.2f}%)" for k, v in sfora.items())
    det += _basenote(base_eff, tot)
    results.append(CheckResult("Circ. 474/D Par.2","474_AIF_SING",f"Singolo OICR non armonizzato (AIF) <= {limite_pct}%",limite_pct,None,max_pct,esito,sc,det,"Par.2 Circ. 474/D",base_eff,tot))
    for isin, pct_v in sfora.items():
        results.append(CheckResult("Circ. 474/D Par.2","474_AIF_SING_DET",f"  -> AIF: {isin}",limite_pct,None,float(pct_v),"SFORAMENTO MAX",round(float(pct_v)-limite_pct,4),f"Valore: €{grp.get(isin,0):,.0f}","Par.2 Circ. 474/D",base_eff,tot))
    return results

_BASE_REG_MAP = {
    "attivo": BASE_TOTALE_ATTIVITA, "attivi": BASE_TOTALE_ATTIVITA,
    "totale_attivita": BASE_TOTALE_ATTIVITA, "totale attivita": BASE_TOTALE_ATTIVITA,
    "patrimonio": BASE_NAV, "nav": BASE_NAV, "netto": BASE_NAV,
    "valore_complessivo": BASE_NAV, "fondo": BASE_NAV,
    "categoria": BASE_CATEGORIA,
}

def check_regolamento(df, limiti, basi=None):
    col_val = _col(df, "valore_bilancio")
    col_class = _col(df, "security_class")
    col_ptype = _col(df, "product_type")
    col_ind = _col(df, "issuer_industry")
    results = []
    if col_val is None:
        return results
    excl_calc = df.get("escluso_calcolo", pd.Series(False, index=df.index))

    for lim in limiti:
        cat = lim.get("categoria_asset", "")
        lim_max = lim.get("limite_max_pct")
        lim_min = lim.get("limite_min_pct")
        lim_emit = lim.get("limite_emittente_pct")
        sezione = lim.get("sezione", lim.get("articolo", ""))
        base_req = _BASE_REG_MAP.get(str(lim.get("base_calcolo","")).lower().strip(), BASE_NAV)
        if base_req == BASE_CATEGORIA:
            tot, base_eff = _totale(df), BASE_CATEGORIA
        else:
            tot, base_eff = _den(df, basi, base_req)

        sc_set, include_cash, sector_key = match_categoria_reg(cat)
        if col_class and sc_set:
            mask = df[col_class].isin(sc_set)
        else:
            mask = pd.Series(False, index=df.index)
        if include_cash and col_ptype:
            mask |= df[col_ptype].isin({"Cash"})

        industry_note = ""
        if sector_key and col_ind:
            kws = SECTOR_INDUSTRY_MAP.get(sector_key, [])
            if kws:
                ind_mask = df[col_ind].astype(str).str.lower().apply(lambda v: any(k in v for k in kws))
                mask &= ind_mask
                industry_note = f" [filtro settore: {sector_key}]"
        elif sector_key and not col_ind:
            industry_note = " [issuer_industry non disponibile: valore approssimato]"

        mask &= ~excl_calc
        val = df.loc[mask, col_val].sum()
        if base_eff == BASE_CATEGORIA:
            tot = val if val else _totale(df)
        pct = _pct(val, tot)
        any_match = mask.any()
        if not any_match and pct == 0.0:
            esito, sc = "NON RILEVABILE", None
        else:
            esito, sc = _esito(pct, lim_max, lim_min)
        det = f"Categoria '{cat}': €{val:,.0f} ({pct:.2f}%)" + industry_note + _basenote(base_eff, tot)
        results.append(CheckResult(
            norma="Regolamento fondo",
            check_id=f"REG_{cat[:20].upper().replace(' ', '_')}",
            descrizione=cat, limite_max_pct=lim_max, limite_min_pct=lim_min,
            valore_effettivo_pct=pct, esito=esito, scostamento_pp=sc,
            dettaglio=det, articolo=sezione, base_calcolo=base_eff, base_valore=tot,
        ))

        if lim_emit is not None and any_match:
            col_emit = _col(df, "denominazione_emittente")
            if col_emit:
                base_cat = val if val else _totale(df)
                grp = df.loc[mask].groupby(col_emit)[col_val].sum()
                grp_pct = (grp / base_cat * 100).sort_values(ascending=False)
                max_emit_pct = float(grp_pct.iloc[0]) if len(grp_pct) else 0.0
                esito_e, sc_e = _esito(max_emit_pct, lim_emit)
                results.append(CheckResult(
                    norma="Regolamento fondo",
                    check_id=f"REG_EMIT_{cat[:15].upper().replace(' ', '_')}",
                    descrizione=f"  -> Max emittente in '{cat}'",
                    limite_max_pct=lim_emit, limite_min_pct=None,
                    valore_effettivo_pct=max_emit_pct, esito=esito_e, scostamento_pp=sc_e,
                    dettaglio=(f"Max emittente: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_emit_pct:.2f}%)" + _basenote(BASE_CATEGORIA, base_cat)),
                    articolo=sezione, base_calcolo=BASE_CATEGORIA, base_valore=base_cat,
                ))

    costruisci_dettagli(df, results)
    return results


# ===========================================================================
# COSTRUZIONE DETTAGLI PER OGNI CHECK
# Stessa base (res.base_valore) e stessa logica (maschere/esenzioni) del check:
# il semaforo del dettaglio non puo' contraddire l'esito.
#   dettaglio_meta = {"pct_col": <col % o None>, "limite_max", "limite_min",
#                     "warn_ratio", "esente_col"}
# ===========================================================================
def _pos_cols(df):
    return {
        "strumento": _col(df, "denominazione_strumento", "isin"),
        "isin": _col(df, "isin"),
        "sclass": _col(df, "security_class"),
        "ptype": _col(df, "product_type"),
        "ft": _col(df, "fund_type"),
        "emit": _col(df, "denominazione_emittente"),
        "grp": _col(df, "gruppo_emittente"),
        "rating": "rating_norm" if "rating_norm" in df.columns else None,
        "listed": "is_listed" if "is_listed" in df.columns else None,
        "ls": _col(df, "long_short"),
        "val": _col(df, "valore_bilancio"),
    }

def _df_posizioni(df, mask, base, c, extra=None):
    val = c["val"]
    cols, ren = [], {}
    def add(key, label):
        if c.get(key) and c[key] not in cols:
            cols.append(c[key]); ren[c[key]] = label
    add("strumento","Strumento"); add("isin","ISIN"); add("sclass","Classificazione")
    if extra:
        for k,l in extra: add(k,l)
    add("emit","Emittente"); add("val","Valore (EUR)")
    sub = df.loc[mask, cols].rename(columns=ren).copy()
    sub["% su base"] = (df.loc[mask, val] / base * 100).round(4) if base else 0.0
    return sub.sort_values("Valore (EUR)", ascending=False).reset_index(drop=True)

def _agg(df, mask, key_col, base, label):
    val = _col(df, "valore_bilancio")
    g = df.loc[mask].groupby(key_col)[val].sum().sort_values(ascending=False)
    out = g.reset_index(); out.columns = [label, "Valore (EUR)"]
    out["% su base"] = (out["Valore (EUR)"] / base * 100).round(4) if base else 0.0
    return out

def costruisci_dettagli(df, results):
    c = _pos_cols(df); val = c["val"]
    if val is None:
        return results
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    for res in results:
        cid = res.check_id
        base = res.base_valore or 0.0
        if cid.endswith("_DET"):
            continue
        if cid == "474_SHORT" and c["ls"]:
            m = df[c["ls"]].astype(str).str.upper().str.startswith("S") & ~excl
            res.dettaglio_df = _df_posizioni(df, m, base, c); res.dettaglio_meta = {"pct_col": None}
        elif cid == "474_COMMOD" and c["sclass"]:
            KW = ["commodity fund","commodity","commodit","merci","materie prime"]
            m = df[c["sclass"]].astype(str).str.lower().apply(lambda v: any(k in v for k in KW)) & ~excl
            res.dettaglio_df = _df_posizioni(df, m, base, c); res.dettaglio_meta = {"pct_col": None}
        elif cid == "474_MONET":
            m = pd.Series(False, index=df.index)
            if c["sclass"]: m |= df[c["sclass"]].isin(MONETARI_SECURITY_CLASSES)
            if c["ptype"]:  m |= df[c["ptype"]].isin(MONETARI_PRODUCT_TYPES)
            m &= ~excl
            res.dettaglio_df = _df_posizioni(df, m, base, c, extra=[("ptype","Tipo prodotto")]); res.dettaglio_meta = {"pct_col": None}
        elif cid == "474_NQUOT" and c["listed"]:
            m = (~df["is_listed"]) & ~excl
            res.dettaglio_df = _df_posizioni(df, m, base, c, extra=[("listed","Quotato")]); res.dettaglio_meta = {"pct_col": None}
        elif cid == "474_RATING" and c["rating"]:
            def _below(row):
                if excl.at[row.name]: return False
                if c["sclass"] and str(row.get("security_class","")).strip() in AZIONARIO_CLASSES: return False
                r = str(row.get("rating_norm","NR")).strip()
                return r == "NR" or r not in RATING_MIN_474
            m = df.apply(_below, axis=1)
            res.dettaglio_df = _df_posizioni(df, m, base, c, extra=[("rating","Rating")]); res.dettaglio_meta = {"pct_col": None}
        elif cid == "474_EMIT" and c["emit"]:
            dfw = df.loc[~excl].copy()
            STATI = ["govt bond","government bond","titoli di stato"]
            dfw["_es"] = dfw.apply(lambda r: (any(k in str(r.get("security_class","")).lower() for k in STATI) or str(r.get("issuer_type","")).lower()=="government") and str(r.get("rating_norm","")).strip()=="AAA", axis=1)
            tot_e = dfw.groupby(c["emit"])[val].sum(); es_e = dfw.loc[dfw["_es"]].groupby(c["emit"])[val].sum()
            out = tot_e.reset_index(); out.columns = ["Emittente","Valore totale (EUR)"]
            out["di cui esente Gov AAA"] = out["Emittente"].map(es_e).fillna(0.0)
            out["Valore soggetto a limite"] = out["Valore totale (EUR)"] - out["di cui esente Gov AAA"]
            out["% soggetto su base"] = (out["Valore soggetto a limite"] / base * 100).round(4) if base else 0.0
            out["Esente"] = out["di cui esente Gov AAA"] > 0
            res.dettaglio_df = out.sort_values("Valore totale (EUR)", ascending=False).reset_index(drop=True)
            res.dettaglio_meta = {"pct_col":"% soggetto su base","limite_max":res.limite_max_pct,"warn_ratio":0.8,"esente_col":"Esente"}
        elif cid == "474_GRUPPO" and c["grp"]:
            res.dettaglio_df = _agg(df, ~excl, c["grp"], base, "Gruppo emittente")
            res.dettaglio_meta = {"pct_col":"% su base","limite_max":res.limite_max_pct,"warn_ratio":0.8}
        elif cid == "474_AIF" and c["ft"]:
            m = (~excl) & (df[c["ft"]].astype(str).str.upper()=="AIF")
            if c["sclass"]: m &= df[c["sclass"]].isin(OICR_CLASSES)
            key = c["isin"] or c["strumento"]
            res.dettaglio_df = _agg(df, m, key, base, "OICR (ISIN)") if m.any() else _df_posizioni(df, m, base, c)
            res.dettaglio_meta = {"pct_col": None}
        elif cid == "474_UCITS" and c["ft"]:
            m = (~excl) & (df[c["ft"]].astype(str).str.upper()=="UCITS")
            if c["sclass"]: m &= df[c["sclass"]].isin(OICR_CLASSES)
            key = c["isin"] or c["strumento"]
            res.dettaglio_df = _agg(df, m, key, base, "OICR UCITS (ISIN)")
            res.dettaglio_meta = {"pct_col":"% su base","limite_max":res.limite_max_pct,"warn_ratio":0.8}
        elif cid == "474_AIF_SING" and c["ft"]:
            m = (~excl) & (df[c["ft"]].astype(str).str.upper()=="AIF")
            if c["sclass"]: m &= df[c["sclass"]].isin(OICR_CLASSES)
            key = c["isin"] or c["strumento"]
            res.dettaglio_df = _agg(df, m, key, base, "OICR AIF (ISIN)")
            res.dettaglio_meta = {"pct_col":"% su base","limite_max":res.limite_max_pct,"warn_ratio":0.8}
        elif cid.startswith("REG_EMIT_") and c["emit"]:
            cat = res.descrizione.split("'")[1] if "'" in res.descrizione else res.descrizione
            m = _mask_categoria(df, cat, c["sclass"], c["ptype"], _col(df,"issuer_industry"))
            res.dettaglio_df = _agg(df, m, c["emit"], base, "Emittente")
            res.dettaglio_meta = {"pct_col":"% su base","limite_max":res.limite_max_pct,"warn_ratio":0.8}
        elif cid.startswith("REG_"):
            cat = res.descrizione
            m = _mask_categoria(df, cat, c["sclass"], c["ptype"], _col(df,"issuer_industry"))
            res.dettaglio_df = _df_posizioni(df, m, base, c); res.dettaglio_meta = {"pct_col": None}
    return results


def esegui_tutti_check(df, limiti_regolamento=None, limite_non_quotati=10.0, tipo_fondo="non previdenziale", basi=None):
    results = []
    results.append(check_short_selling(df, basi))
    results.append(check_commodities(df, basi))
    results.append(check_monetari(df, basi))
    results.append(check_non_quotati(df, limite_non_quotati, tipo_fondo, basi))
    results.append(check_rating_minimo(df, basi=basi))
    results.extend(check_concentrazione_emittente(df, basi=basi))
    results.extend(check_concentrazione_gruppo(df, basi=basi))
    results.append(check_oicr_non_armonizzati(df, basi=basi))
    results.extend(check_singolo_ucits(df, basi=basi))
    results.extend(check_singolo_aif(df, basi=basi))
    if limiti_regolamento:
        results.extend(check_regolamento(df, limiti_regolamento, basi))
    costruisci_dettagli(df, results)
    return results

"""
analisi_474.py
Motore di verifica dei limiti della Circolare ISVAP 474/D (fondi interni UL/IL).
Ogni check è una funzione autonoma che restituisce un dizionario con:
  - descrizione, valore_effettivo_pct, limite_pct, esito, dettaglio
"""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Costanti regolamentari (Sezione 3 Circolare 474/D)
# ---------------------------------------------------------------------------

# Security Classification che rappresentano fondi (OICR)
OICR_CLASSES = {
    "Money market fund", "Real Estate fund", "Fixed Income fund",
    "Mixed fund", "Hedge fund", "Equity fund",
}

# Security Classification che rappresentano strumenti monetari
MONETARI_CLASSES = {
    "Money market fund",       # OICR monetario
}
# Product types monetari diretti
MONETARI_PRODUCT_TYPES = {
    "Cash",
}
# Security Class diretti che sono monetari
MONETARI_SECURITY_CLASSES = {
    "Money market fund",
}

# Security Classification assimilabili ad azioni / azionari (escluse dal minimo rating)
AZIONARIO_CLASSES = {
    "Share", "Equity fund", "Real Estate Shares", "Private Equities",
}

# Strumenti da escludere dal denominatore
ESCLUSI_PRODUCT_TYPES = {
    "Repurchase Agreement", "Interest rate swap (IRS)", "FX Forward",
    "Credit Default Swap (CDS)", "Securities  Forward",
    "Other P/L Items", "Repo Collateral Margin Account",
}

RATING_ORDER_SP = [
    "AAA","AA+","AA","AA-",
    "A+","A","A-",
    "BBB+","BBB","BBB-",
    "BB+","BB","BB-",
    "B+","B","B-",
    "CCC+","CCC","CCC-","CC","C","D",
]
RATING_MIN_474 = set(RATING_ORDER_SP[:RATING_ORDER_SP.index("BB") + 1])  # ≥ BB


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _col(df: pd.DataFrame, *candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _totale(df: pd.DataFrame) -> float:
    """Totale portafoglio escludendo derivati/repo."""
    col = _col(df, "valore_mercato", "valore_bilancio")
    if col is None:
        return 0.0
    mask_esclusi = (
        df.get("product_type", pd.Series(dtype=str)).isin(ESCLUSI_PRODUCT_TYPES)
        | df.get("security_class", pd.Series(dtype=str)).isin({"Not assigned"})
        .combine(df.get("product_type", pd.Series(dtype=str)).isin(ESCLUSI_PRODUCT_TYPES), lambda a, b: a & b)
    )
    # Più semplice: usa la flag già calcolata dal parser
    if "escluso_calcolo" in df.columns:
        return float(df.loc[~df["escluso_calcolo"], col].sum())
    return float(df[col].sum())


def _pct(valore: float, totale: float) -> float:
    if totale == 0:
        return 0.0
    return round(valore / totale * 100, 4)


def _is_azionario(row: pd.Series) -> bool:
    sc = str(row.get("security_class", "")).strip()
    return sc in AZIONARIO_CLASSES


def _rating_below_bb(row: pd.Series) -> bool:
    """True se il titolo ha rating < BB o NR (e non è azionario)."""
    if _is_azionario(row):
        return False
    r = str(row.get("rating_norm", "NR")).strip()
    return r == "NR" or r not in RATING_MIN_474


def _esito(valore_pct: float, limite_pct: float | None,
           minimo_pct: float | None = None) -> tuple[str, float | None]:
    """Restituisce (esito, scostamento)."""
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
# CHECK 1 — Vendite allo scoperto (Short selling vietato)
# ---------------------------------------------------------------------------

def check_short_selling(df: pd.DataFrame) -> CheckResult:
    col = _col(df, "long_short")
    if col is None:
        short_pct = 0.0
        det = "Colonna Long/Short non presente nel SHIP"
    else:
        tot = _totale(df)
        short_val = df.loc[df[col].astype(str).str.lower() == "short", "valore_mercato"].sum()
        short_pct = _pct(short_val, tot)
        det = f"Posizioni short: {short_pct:.2f}% del portafoglio"

    esito, sc = _esito(short_pct, 0.0)
    return CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_SHORT",
        descrizione="Divieto vendite allo scoperto",
        limite_max_pct=0.0,
        limite_min_pct=None,
        valore_effettivo_pct=short_pct,
        esito=esito if short_pct > 0 else "OK",
        scostamento_pp=sc if short_pct > 0 else None,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    )


# ---------------------------------------------------------------------------
# CHECK 2 — Divieto investimenti in merci / commodities
# ---------------------------------------------------------------------------

def check_commodities(df: pd.DataFrame) -> CheckResult:
    COMMOD_KEYWORDS = ["commodity", "commodit", "merci", "materie prime"]
    col = _col(df, "security_class", "valuation_class")
    if col is None:
        commod_pct = 0.0
        det = "Colonna classificazione non presente"
    else:
        tot = _totale(df)
        col_val = _col(df, "valore_mercato", "valore_bilancio")
        mask = df[col].astype(str).str.lower().apply(
            lambda v: any(kw in v for kw in COMMOD_KEYWORDS)
        )
        commod_pct = _pct(df.loc[mask, col_val].sum(), tot) if col_val else 0.0
        det = f"Strumenti commodity rilevati: {mask.sum()} posizioni ({commod_pct:.2f}%)"

    esito, sc = ("OK", None) if commod_pct == 0 else ("SFORAMENTO MAX", commod_pct)
    return CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_COMMOD",
        descrizione="Divieto investimento in merci / commodities",
        limite_max_pct=0.0,
        limite_min_pct=None,
        valore_effettivo_pct=commod_pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    )


# ---------------------------------------------------------------------------
# CHECK 3 — Limite strumenti monetari ≤ 20%
# ---------------------------------------------------------------------------

def check_monetari(df: pd.DataFrame) -> CheckResult:
    LIMITE = 20.0
    col_class = _col(df, "security_class", "valuation_class")
    col_ptype = _col(df, "product_type")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if col_val is None or tot == 0:
        return CheckResult("Circ. 474/D §2", "474_MONET",
                           "Strumenti monetari ≤ 20%", LIMITE, None,
                           0.0, "NON RILEVABILE", None,
                           "Colonna valore non trovata")

    mask = pd.Series(False, index=df.index)
    if col_class:
        mask |= df[col_class].isin(MONETARI_SECURITY_CLASSES)
    if col_ptype:
        mask |= df[col_ptype].isin(MONETARI_PRODUCT_TYPES)

    # Includi anche i pronti contro termine (monetari)
    if col_ptype:
        mask |= df[col_ptype].astype(str).str.lower().str.contains("repo|pronti|money market", na=False)

    val = df.loc[mask, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, LIMITE)
    det = (f"Strumenti monetari: €{val:,.0f} ({pct:.2f}% su tot. €{tot:,.0f}). "
           f"Posizioni: {mask.sum()}")
    return CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_MONET",
        descrizione="Strumenti monetari ≤ 20% del fondo",
        limite_max_pct=LIMITE,
        limite_min_pct=None,
        valore_effettivo_pct=pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    )


# ---------------------------------------------------------------------------
# CHECK 4 — Limite titoli non quotati ≤ 10% (non previdenziale) / 25% (prev.)
# ---------------------------------------------------------------------------

def check_non_quotati(df: pd.DataFrame,
                      limite_pct: float = 10.0,
                      tipo_fondo: str = "non previdenziale") -> CheckResult:
    col_listed = _col(df, "is_listed", "listed")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if col_val is None or tot == 0:
        return CheckResult("Circ. 474/D §2", "474_NQUOT",
                           f"Non quotati ≤ {limite_pct}%", limite_pct, None,
                           0.0, "NON RILEVABILE", None)

    if col_listed == "is_listed":
        mask_nq = ~df["is_listed"]
    elif col_listed == "listed":
        mask_nq = df["listed"].astype(str).str.strip().str.upper() != "X"
    else:
        mask_nq = pd.Series(False, index=df.index)

    # Escludi derivati/repo dal conteggio
    if "escluso_calcolo" in df.columns:
        mask_nq &= ~df["escluso_calcolo"]

    val = df.loc[mask_nq, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)

    # Breakdown per categoria
    col_class = _col(df, "security_class")
    if col_class:
        breakdown = df.loc[mask_nq].groupby(col_class)[col_val].sum().sort_values(ascending=False)
        det_parts = [f"{k}: €{v:,.0f}" for k, v in breakdown.head(5).items()]
        det = f"Non quotati: {pct:.2f}%. Top categorie: {'; '.join(det_parts)}"
    else:
        det = f"Non quotati: €{val:,.0f} ({pct:.2f}%)"

    return CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_NQUOT",
        descrizione=f"Titoli non quotati ≤ {limite_pct}% ({tipo_fondo})",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    )


# ---------------------------------------------------------------------------
# CHECK 5 — Rating minimo BB (titoli < BB o NR ≤ 5%)
# ---------------------------------------------------------------------------

def check_rating_minimo(df: pd.DataFrame, limite_pct: float = 5.0) -> CheckResult:
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if col_val is None or tot == 0 or "rating_norm" not in df.columns:
        return CheckResult("Circ. 474/D §1", "474_RATING",
                           f"Rating < BB o NR ≤ {limite_pct}%", limite_pct, None,
                           0.0, "NON RILEVABILE", None, "Colonna rating non disponibile")

    # Maschera titoli sotto soglia (esclude azionari e derivati)
    col_class = _col(df, "security_class")
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))

    def _is_below(row):
        if excl.at[row.name]:
            return False
        sc = str(row.get("security_class", "")).strip() if col_class else ""
        if sc in AZIONARIO_CLASSES:
            return False
        r = str(row.get("rating_norm", "NR")).strip()
        return r == "NR" or r not in RATING_MIN_474

    mask_below = df.apply(_is_below, axis=1)
    val = df.loc[mask_below, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)

    # Dettaglio distribuzione rating
    if "rating_norm" in df.columns:
        rating_dist = (df.loc[mask_below]
                       .groupby("rating_norm")[col_val].sum()
                       .sort_values(ascending=False))
        det_parts = [f"{k}: €{v:,.0f}" for k, v in rating_dist.head(5).items()]
        det = f"< BB o NR: {pct:.2f}%. Distribuzione: {'; '.join(det_parts)}"
    else:
        det = f"< BB o NR: €{val:,.0f} ({pct:.2f}%)"

    return CheckResult(
        norma="Circ. 474/D §1",
        check_id="474_RATING",
        descrizione=f"Titoli rating < BB o NR ≤ {limite_pct}% del fondo",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§1 Circ. 474/D",
    )


# ---------------------------------------------------------------------------
# CHECK 6 — Limite per singolo emittente ≤ 10%
#           (esclusi titoli di Stato UE e sovrannazionali con rating AAA)
# ---------------------------------------------------------------------------

def check_concentrazione_emittente(df: pd.DataFrame,
                                   limite_pct: float = 10.0) -> list[CheckResult]:
    """
    Restituisce un CheckResult sintetico (max emittente)
    + una lista di emittenti in sforamento.
    """
    col_emit = _col(df, "denominazione_emittente")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    col_class = _col(df, "security_class")
    tot = _totale(df)

    if not col_emit or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D §2", "474_EMIT",
                            f"Concentrazione per emittente ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None,
                            "Colonna emittente o valore non trovata")]

    # Esclude derivati/repo e Titoli di Stato UE con rating ≥ AAA (esentati)
    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    df_work = df.loc[~excl].copy()

    # Identifica titoli esenti (gov bonds UE o sovrannazionali AAA)
    STATI_UE_KEY = ["govt bond", "government bond", "titoli di stato"]
    def _esentato(row):
        sc = str(row.get("security_class", "")).lower()
        is_gov = any(k in sc for k in STATI_UE_KEY) or str(row.get("issuer_type","")).lower() == "government"
        rating = str(row.get("rating_norm","")).strip()
        return is_gov and rating == "AAA"

    df_work["_esentato"] = df_work.apply(_esentato, axis=1)
    df_calc = df_work.loc[~df_work["_esentato"]]

    grp = df_calc.groupby(col_emit)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)

    max_pct = float(grp_pct.iloc[0]) if len(grp_pct) > 0 else 0.0
    emit_sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    top5 = "; ".join(f"{k}: {v:.2f}%" for k, v in grp_pct.head(5).items())
    det = f"Emittente max: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_pct:.2f}%). Top 5: {top5}"
    if len(emit_sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k, v in emit_sfora.items())}"

    results.append(CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_EMIT",
        descrizione=f"Concentrazione emittente ≤ {limite_pct}% (ex Gov AAA)",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=max_pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    ))

    # Una riga per ogni emittente in sforamento
    for emit, pct_v in emit_sfora.items():
        results.append(CheckResult(
            norma="Circ. 474/D §2",
            check_id="474_EMIT_DET",
            descrizione=f"  ↳ Emittente: {emit}",
            limite_max_pct=limite_pct,
            limite_min_pct=None,
            valore_effettivo_pct=float(pct_v),
            esito="SFORAMENTO MAX",
            scostamento_pp=round(float(pct_v) - limite_pct, 4),
            dettaglio=f"Valore: €{grp.get(emit, 0):,.0f}",
            articolo="§2 Circ. 474/D",
        ))

    return results


# ---------------------------------------------------------------------------
# CHECK 7 — Limite per gruppo di controllo ≤ 30%
# ---------------------------------------------------------------------------

def check_concentrazione_gruppo(df: pd.DataFrame,
                                 limite_pct: float = 30.0) -> list[CheckResult]:
    col_gruppo = _col(df, "gruppo_emittente")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if not col_gruppo or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D §2", "474_GRUPPO",
                            f"Concentrazione gruppo ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None,
                            "Colonna 'Issuer Ultimate Parent' non trovata")]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    grp = (df.loc[~excl]
             .groupby(col_gruppo)[col_val].sum()
             .sort_values(ascending=False))
    grp_pct = (grp / tot * 100).round(4)

    max_pct = float(grp_pct.iloc[0]) if len(grp_pct) > 0 else 0.0
    gruppi_sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    top5 = "; ".join(f"{k}: {v:.2f}%" for k, v in grp_pct.head(5).items())
    det = f"Gruppo max: {grp_pct.index[0] if len(grp_pct) else 'N/A'} ({max_pct:.2f}%). Top 5: {top5}"
    if len(gruppi_sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k, v in gruppi_sfora.items())}"

    results.append(CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_GRUPPO",
        descrizione=f"Concentrazione gruppo emittente ≤ {limite_pct}%",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=max_pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D (circ. 551 integraz.)",
    ))

    for gruppo, pct_v in gruppi_sfora.items():
        results.append(CheckResult(
            norma="Circ. 474/D §2",
            check_id="474_GRUPPO_DET",
            descrizione=f"  ↳ Gruppo: {gruppo}",
            limite_max_pct=limite_pct,
            limite_min_pct=None,
            valore_effettivo_pct=float(pct_v),
            esito="SFORAMENTO MAX",
            scostamento_pp=round(float(pct_v) - limite_pct, 4),
            dettaglio=f"Valore: €{grp.get(gruppo, 0):,.0f}",
            articolo="§2 Circ. 474/D",
        ))

    return results


# ---------------------------------------------------------------------------
# CHECK 8 — OICR non armonizzati (AIF) ≤ 30% complessivo
# ---------------------------------------------------------------------------

def check_oicr_non_armonizzati(df: pd.DataFrame,
                                limite_pct: float = 30.0) -> CheckResult:
    col_ft = _col(df, "fund_type")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if not col_ft or col_val is None or tot == 0:
        return CheckResult("Circ. 474/D §2", "474_AIF",
                           f"OICR non armonizzati (AIF) ≤ {limite_pct}%",
                           limite_pct, None, 0.0, "NON RILEVABILE", None,
                           "Colonna Fund Type non disponibile")

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    mask = (~excl) & (df[col_ft].astype(str).str.upper() == "AIF")
    val = df.loc[mask, col_val].sum()
    pct = _pct(val, tot)
    esito, sc = _esito(pct, limite_pct)

    # Breakdown per security class
    col_class = _col(df, "security_class")
    if col_class:
        bd = df.loc[mask].groupby(col_class)[col_val].sum().sort_values(ascending=False)
        det_parts = [f"{k}: €{v:,.0f}" for k, v in bd.items()]
        det = f"AIF totale: {pct:.2f}%. Categorie: {'; '.join(det_parts)}"
    else:
        det = f"AIF totale: €{val:,.0f} ({pct:.2f}%)"

    return CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_AIF",
        descrizione=f"OICR non armonizzati (AIF) ≤ {limite_pct}% del fondo",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    )


# ---------------------------------------------------------------------------
# CHECK 9 — Singolo OICR armonizzato (UCITS) ≤ 25%
# ---------------------------------------------------------------------------

def check_singolo_ucits(df: pd.DataFrame,
                         limite_pct: float = 25.0) -> list[CheckResult]:
    col_ft = _col(df, "fund_type")
    col_isin = _col(df, "isin", "denominazione_strumento")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if not col_ft or not col_isin or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D §2", "474_UCITS",
                            f"Singolo OICR UCITS ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None,
                            "Colonne Fund Type / ISIN non disponibili")]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    mask_ucits = (~excl) & (df[col_ft].astype(str).str.upper() == "UCITS")
    df_ucits = df.loc[mask_ucits]

    if df_ucits.empty:
        return [CheckResult("Circ. 474/D §2", "474_UCITS",
                            f"Singolo OICR UCITS ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "OK", None,
                            "Nessun OICR UCITS presente")]

    grp = df_ucits.groupby(col_isin)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0])
    sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    det = f"Max singolo UCITS: {grp_pct.index[0]} ({max_pct:.2f}%)"
    if len(sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k,v in sfora.items())}"

    results.append(CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_UCITS",
        descrizione=f"Singolo OICR UCITS ≤ {limite_pct}%",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=max_pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    ))

    for isin, pct_v in sfora.items():
        results.append(CheckResult(
            norma="Circ. 474/D §2",
            check_id="474_UCITS_DET",
            descrizione=f"  ↳ UCITS: {isin}",
            limite_max_pct=limite_pct,
            limite_min_pct=None,
            valore_effettivo_pct=float(pct_v),
            esito="SFORAMENTO MAX",
            scostamento_pp=round(float(pct_v) - limite_pct, 4),
            dettaglio=f"Valore: €{grp.get(isin, 0):,.0f}",
            articolo="§2 Circ. 474/D",
        ))

    return results


# ---------------------------------------------------------------------------
# CHECK 10 — Singolo OICR non armonizzato (AIF) ≤ 10%
# ---------------------------------------------------------------------------

def check_singolo_aif(df: pd.DataFrame,
                       limite_pct: float = 10.0) -> list[CheckResult]:
    col_ft = _col(df, "fund_type")
    col_isin = _col(df, "isin", "denominazione_strumento")
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    tot = _totale(df)

    if not col_ft or not col_isin or col_val is None or tot == 0:
        return [CheckResult("Circ. 474/D §2", "474_AIF_SING",
                            f"Singolo OICR AIF ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "NON RILEVABILE", None)]

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    mask_aif = (~excl) & (df[col_ft].astype(str).str.upper() == "AIF")
    df_aif = df.loc[mask_aif]

    if df_aif.empty:
        return [CheckResult("Circ. 474/D §2", "474_AIF_SING",
                            f"Singolo OICR AIF ≤ {limite_pct}%",
                            limite_pct, None, 0.0, "OK", None,
                            "Nessun OICR AIF presente")]

    grp = df_aif.groupby(col_isin)[col_val].sum().sort_values(ascending=False)
    grp_pct = (grp / tot * 100).round(4)
    max_pct = float(grp_pct.iloc[0])
    sfora = grp_pct[grp_pct > limite_pct]

    results = []
    esito, sc = _esito(max_pct, limite_pct)
    det = f"Max singolo AIF: {grp_pct.index[0]} ({max_pct:.2f}%)"
    if len(sfora):
        det += f" | SFORA: {', '.join(f'{k} ({v:.2f}%)' for k,v in sfora.items())}"

    results.append(CheckResult(
        norma="Circ. 474/D §2",
        check_id="474_AIF_SING",
        descrizione=f"Singolo OICR non armonizzato (AIF) ≤ {limite_pct}%",
        limite_max_pct=limite_pct,
        limite_min_pct=None,
        valore_effettivo_pct=max_pct,
        esito=esito,
        scostamento_pp=sc,
        dettaglio=det,
        articolo="§2 Circ. 474/D",
    ))

    for isin, pct_v in sfora.items():
        results.append(CheckResult(
            norma="Circ. 474/D §2",
            check_id="474_AIF_SING_DET",
            descrizione=f"  ↳ AIF: {isin}",
            limite_max_pct=limite_pct,
            limite_min_pct=None,
            valore_effettivo_pct=float(pct_v),
            esito="SFORAMENTO MAX",
            scostamento_pp=round(float(pct_v) - limite_pct, 4),
            dettaglio=f"Valore: €{grp.get(isin, 0):,.0f}",
            articolo="§2 Circ. 474/D",
        ))

    return results


# ---------------------------------------------------------------------------
# CHECK REGOLAMENTO — limiti definiti nel regolamento del fondo
# (flessibile: riceve lista dizionari estratti da Claude)
# ---------------------------------------------------------------------------

def check_regolamento(df: pd.DataFrame,
                       limiti: list[dict]) -> list[CheckResult]:
    """
    Verifica i limiti estratti dal regolamento del fondo.
    Supporta:
      - categoria_asset: matching per security_class / valuation_class
      - limite_max_pct / limite_min_pct
      - limite_emittente_pct: max singolo emittente sul sottoinsieme
    """
    col_val = _col(df, "valore_mercato", "valore_bilancio")
    col_class = _col(df, "security_class", "valuation_class")
    tot = _totale(df)
    results = []

    if col_val is None or tot == 0:
        return results

    # Mappa macro-categoria → lista security_class
    MACRO_MAP = {
        "obbligazionari": {
            "Govt bonds <1 year", "Govt bonds >1 year <10 years", "Govt bonds >10 years",
            "Ordinary bond", "Subordinated bond", "Infra Bonds", "Index Linked Bonds",
            "Mortgage Backed Security", "Asset Backed Security", "Perpetual Notes",
            "Credit linked note",
        },
        "azionari": {"Share", "Real Estate Shares", "Private Equities"},
        "immobiliari": {"Real Estate fund", "Real Estate Shares"},
        "fondi": {"Fixed Income fund", "Mixed fund", "Hedge fund", "Equity fund",
                  "Real Estate fund", "Money market fund"},
        "liquidità": {"Money market fund"},
        "altri strumenti": {"Fixed Income fund", "Private equity fund", "Mixed fund",
                            "Hedge fund", "Real Estate fund", "Equity fund",
                            "Money market fund"},
    }

    def _match_classes(cat_str: str) -> set[str]:
        cat_lower = cat_str.lower().strip()
        for macro, sc_set in MACRO_MAP.items():
            if macro in cat_lower:
                return sc_set
        return {cat_str}  # uso letterale come fallback

    for lim in limiti:
        cat = lim.get("categoria_asset", "")
        lim_max = lim.get("limite_max_pct")
        lim_min = lim.get("limite_min_pct")
        lim_emit = lim.get("limite_emittente_pct")
        sezione = lim.get("sezione", lim.get("articolo", ""))

        # Calcola % della categoria
        sc_set = _match_classes(cat) if col_class else set()
        if col_class and sc_set:
            mask = df[col_class].isin(sc_set)
        else:
            mask = pd.Series(False, index=df.index)

        val = df.loc[mask, col_val].sum()
        pct = _pct(val, tot)
        any_match = mask.any()

        if not any_match and pct == 0.0:
            esito = "NON RILEVABILE"
            sc = None
        else:
            esito, sc = _esito(pct, lim_max, lim_min)

        det = f"Categoria '{cat}': €{val:,.0f} ({pct:.2f}% del tot. €{tot:,.0f})"

        results.append(CheckResult(
            norma="Regolamento fondo",
            check_id=f"REG_{cat[:20].upper().replace(' ','_')}",
            descrizione=f"{cat}",
            limite_max_pct=lim_max,
            limite_min_pct=lim_min,
            valore_effettivo_pct=pct,
            esito=esito,
            scostamento_pp=sc,
            dettaglio=det,
            articolo=sezione,
        ))

        # Check emittente sul sottoinsieme
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
# Runner principale — esegue tutti i check 474 + regolamento
# ---------------------------------------------------------------------------

def esegui_tutti_check(
    df: pd.DataFrame,
    limiti_regolamento: list[dict] | None = None,
    limite_non_quotati: float = 10.0,
    tipo_fondo: str = "non previdenziale",
) -> list[CheckResult]:
    """
    Esegue l'intera batteria di check.
    Restituisce lista CheckResult ordinata per check_id.
    """
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

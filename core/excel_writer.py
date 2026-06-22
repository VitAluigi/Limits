"""
excel_writer.py
Genera l'output Excel formattato con tutti i check 474 e regolamento.
"""

import io
import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from core.analisi import CheckResult

# -- Palette ------------------------------------------------------------------
C_BLUE = "00338D"
C_BLUE_LT = "4472C4"
C_WHITE = "FFFFFF"
C_BLACK = "000000"
C_STRIPE = "F2F2F2"
C_OK = "C6EFCE"   # verde chiaro
C_WARN = "FFEB9C"   # giallo
C_ERR = "FFC7CE"   # rosso chiaro
C_BORDER = "BFBFBF"
C_GRAY = "D9D9D9"
C_HEADER_REG = "2E75B6"

FONT_BODY = "Arial"
FONT_LOGO = "KPMG Logo"
FONT_BOLD = "KPMG Bold"
SZ = 8
SZ_HEAD = 14


def _side():
    return Side(style="thin", color=C_BORDER)


def _border():
    s = _side()
    return Border(left=s, right=s, top=s, bottom=s)


def _header_cell(ws, row, col, value, bg=C_BLUE):
    c = ws.cell(row, col, str(value))
    c.font = Font(name=FONT_BODY, size=SZ, bold=True, color=C_WHITE)
    c.fill = PatternFill("solid", start_color=bg)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = _border()
    ws.row_dimensions[row].height = 20


def _data_cell(ws, row, col, value, stripe=False, fmt=None):
    c = ws.cell(row, col, value)
    c.font = Font(name=FONT_BODY, size=SZ, color=C_BLACK)
    c.alignment = Alignment(vertical="center")
    c.border = _border()
    c.fill = PatternFill("solid", start_color=(C_STRIPE if stripe else C_WHITE))
    if fmt:
        c.number_format = fmt
    ws.row_dimensions[row].height = 12


def _kpmg_logo(ws, title: str):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2
    ws["B2"].value = "kpmg"
    ws["B2"].font = Font(name=FONT_LOGO, size=SZ_HEAD, color=C_BLUE)
    ws["B2"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 20
    ws["B3"].value = title
    ws["B3"].font = Font(name=FONT_BOLD, size=SZ_HEAD, bold=True, color=C_BLUE)
    ws["B3"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[3].height = 20
    ws.row_dimensions[4].height = 6


def _auto_width(ws, start_col=2, min_w=8, max_w=60):
    for col in ws.iter_cols(min_col=start_col):
        w = min_w
        for cell in col:
            if cell.value:
                w = max(w, min(len(str(cell.value)) + 3, max_w))
        ws.column_dimensions[get_column_letter(col[0].column)].width = w


ESITO_COLOR = {
    "OK": C_OK,
    "SFORAMENTO MAX": C_ERR,
    "SFORAMENTO EMITTENTE": C_ERR,
    "SOTTO MINIMO": C_WARN,
    "NON RILEVABILE": C_GRAY,
    "AVVISO": C_WARN,
}

HEADERS_474 = [
    "Norma", "Check", "Descrizione", "Art./Par.",
    "Limite MAX %", "Limite MIN %",
    "Valore effettivo %", "Esito", "Scostamento pp", "Dettaglio"
]


def _write_check_sheet(ws, results: list[CheckResult], title: str,
                        header_bg=C_BLUE):
    _kpmg_logo(ws, title)

    if not results:
        ws["B5"].value = "Nessun check disponibile."
        ws["B5"].font = Font(name=FONT_BODY, size=SZ, color=C_BLACK)
        return

    for j, h in enumerate(HEADERS_474, 2):
        _header_cell(ws, 5, j, h, bg=header_bg)

    for i, r in enumerate(results, 6):
        bg_row = ESITO_COLOR.get(r.esito, C_WHITE)
        stripe = (i % 2 == 0)
        vals = [
            r.norma, r.check_id, r.descrizione, r.articolo,
            r.limite_max_pct, r.limite_min_pct,
            r.valore_effettivo_pct, r.esito, r.scostamento_pp, r.dettaglio,
        ]
        ws.row_dimensions[i].height = 12
        for j, val in enumerate(vals, 2):
            c = ws.cell(i, j, val)
            c.font = Font(name=FONT_BODY, size=SZ, color=C_BLACK)
            c.alignment = Alignment(vertical="center")
            c.border = _border()
            c.fill = PatternFill("solid", start_color=bg_row)
            # Formato numerico per le colonne %
            if j in (6, 7, 8, 10) and isinstance(val, (int, float)):
                c.number_format = '0.00"%"'

    _auto_width(ws)


def _write_db_sheet(ws, df: pd.DataFrame):
    if df.empty:
        return
    for j, col in enumerate(df.columns, 1):
        c = ws.cell(1, j, str(col))
        c.font = Font(name=FONT_BODY, size=SZ, bold=True)
        c.alignment = Alignment(vertical="center")
    for i, row in enumerate(df.itertuples(index=False), 2):
        for j, val in enumerate(row, 1):
            c = ws.cell(i, j, val)
            c.font = Font(name=FONT_BODY, size=SZ)
            c.alignment = Alignment(vertical="center")
    for col in ws.columns:
        w = 8
        for cell in col:
            if cell.value:
                w = max(w, min(len(str(cell.value)) + 2, 40))
        ws.column_dimensions[get_column_letter(col[0].column)].width = w


def _write_dettaglio_sheet(ws, df: pd.DataFrame, title: str,
                            col_gruppo: str, col_val: str, totale: float):
    """Sheet di dettaglio concentrazione per emittente/gruppo."""
    _kpmg_logo(ws, title)
    if df.empty or col_gruppo not in df.columns or col_val not in df.columns:
        ws["B5"].value = "Nessun dato disponibile."
        return

    excl = df.get("escluso_calcolo", pd.Series(False, index=df.index))
    grp = (df.loc[~excl]
             .groupby(col_gruppo)[col_val].sum()
             .reset_index()
             .sort_values(col_val, ascending=False)
             .reset_index(drop=True))
    grp["% portafoglio"] = (grp[col_val] / totale * 100).round(4)

    hdrs = [col_gruppo.replace("_", " ").title(), "Valore (EUR)", "% portafoglio"]
    for j, h in enumerate(hdrs, 2):
        _header_cell(ws, 5, j, h)

    for i, row in enumerate(grp.itertuples(index=False), 6):
        stripe = (i % 2 == 0)
        _data_cell(ws, i, 2, row[0], stripe)
        _data_cell(ws, i, 3, row[1], stripe, "#,##0.00")
        c = ws.cell(i, 4, row[2])
        c.font = Font(name=FONT_BODY, size=SZ, color=C_BLACK)
        c.border = _border()
        c.number_format = '0.00"%"'
        # Colore se > 10%
        bg = C_ERR if row[2] > 10 else (C_WARN if row[2] > 5 else (C_STRIPE if stripe else C_WHITE))
        c.fill = PatternFill("solid", start_color=bg)
        ws.row_dimensions[i].height = 12

    _auto_width(ws)


def _write_legend_sheet(ws):
    _kpmg_logo(ws, "Legenda e note metodologiche")
    legenda = [
        ("COLORE", "ESITO", "SIGNIFICATO"),
        ("Verde", "OK", "Limite rispettato"),
        ("Rosso", "SFORAMENTO MAX", "Valore effettivo supera il limite massimo"),
        ("Giallo", "SOTTO MINIMO", "Valore effettivo inferiore al limite minimo"),
        ("Grigio", "NON RILEVABILE", "Impossibile calcolare — dati mancanti o categoria non mappata"),
    ]
    COLORS = [C_BLUE, C_OK, C_ERR, C_WARN, C_GRAY]
    for i, (col_color, esito, desc) in enumerate(legenda, 5):
        bg = COLORS[i - 5]
        for j, val in enumerate([col_color, esito, desc], 2):
            c = ws.cell(i, j, val)
            c.font = Font(name=FONT_BODY, size=SZ,
                          bold=(i == 5), color=C_WHITE if i == 5 else C_BLACK)
            c.fill = PatternFill("solid", start_color=bg)
            c.border = _border()
            c.alignment = Alignment(vertical="center")
        ws.row_dimensions[i].height = 14

    note_row = 11
    ws.cell(note_row, 2, "Note metodologiche:").font = Font(name=FONT_BODY, size=SZ, bold=True)
    note_row += 1
    notes = [
        "- Valore di riferimento: Total Market Value LC (in valuta locale).",
        "- Denominatore: totale portafoglio esclusi derivati OTC, repo, cash collateral.",
        "- Rating: fallback chain S&P > Fitch > Moody's > IFRS9. Titoli azionari esenti.",
        "- Quotato: 'Indicator: Listed on Exchange' = X. Blank = non quotato.",
        "- Limite emittente 474: esclude Gov Bond UE / sovrannazionali con rating AAA.",
        "- Limite gruppo: basato su 'Issuer Ultimate Parent Numb Name' del SHIP.",
        "- I limiti di regolamento sono estratti via Claude AI dal PDF del regolamento.",
    ]
    for note in notes:
        c = ws.cell(note_row, 2, note)
        c.font = Font(name=FONT_BODY, size=SZ, color=C_BLACK)
        ws.row_dimensions[note_row].height = 14
        note_row += 1

    _auto_width(ws)


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------

def genera_excel(
    df_portafoglio: pd.DataFrame,
    results_474: list[CheckResult],
    results_reg: list[CheckResult],
    limiti_regolamento: list[dict],
    info_fondo: dict,
    nome_fondo: str = "Fondo",
) -> bytes:
    wb = Workbook()

    # -- COVER ----------------------------------------------------------------
    ws_cover = wb.active
    ws_cover.title = "Cover"
    ws_cover.sheet_view.showGridLines = False
    ws_cover.column_dimensions["A"].width = 2
    ws_cover.column_dimensions["B"].width = 32
    ws_cover.column_dimensions["C"].width = 48

    ws_cover["B2"].value = "KPMG"
    ws_cover["B2"].font = Font(name=FONT_LOGO, size=18, color=C_BLUE)
    ws_cover["B2"].alignment = Alignment(horizontal="left", vertical="center")
    ws_cover.row_dimensions[2].height = 28

    ws_cover["B3"].value = "Verifica Limiti Fondi Interni UL — Circolare ISVAP 474/D"
    ws_cover["B3"].font = Font(name=FONT_BOLD, size=14, bold=True, color=C_BLUE)
    ws_cover["B3"].alignment = Alignment(horizontal="left", vertical="center")
    ws_cover.row_dimensions[3].height = 22

    ws_cover["B4"].value = nome_fondo
    ws_cover["B4"].font = Font(name=FONT_BODY, size=11, color=C_BLUE)
    ws_cover.row_dimensions[4].height = 18
    ws_cover.row_dimensions[5].height = 10

    col_val = "valore_mercato" if "valore_mercato" in df_portafoglio.columns else "valore_bilancio"
    excl = df_portafoglio.get("escluso_calcolo", pd.Series(False, index=df_portafoglio.index))
    tot = df_portafoglio.loc[~excl, col_val].sum() if col_val in df_portafoglio.columns else 0

    meta = [
        ("Fondo / Gestione", info_fondo.get("nome_fondo", nome_fondo)),
        ("Tipo", info_fondo.get("tipo", "—")),
        ("Compagnia", info_fondo.get("compagnia", "—")),
        ("Tipo prestazione", info_fondo.get("tipo_prestazione", "non_previdenziale")),
        ("Data elaborazione", datetime.date.today().strftime("%d/%m/%Y")),
        ("N. posizioni", f"{len(df_portafoglio):,}"),
        ("Totale portafoglio", f"€ {tot:,.2f}"),
        ("Check 474 eseguiti", str(len(results_474))),
        ("Check regolamento", str(len(results_reg))),
    ]
    for r, (lbl, val) in enumerate(meta, 6):
        lc = ws_cover.cell(r, 2, lbl)
        lc.font = Font(name=FONT_BODY, size=9, bold=True)
        vc = ws_cover.cell(r, 3, val)
        vc.font = Font(name=FONT_BODY, size=9)
        ws_cover.row_dimensions[r].height = 16

    # -- SHEET 474 -------------------------------------------------------------
    ws_474 = wb.create_sheet("Verifica_474")
    _write_check_sheet(ws_474, results_474,
                       "Verifica limiti — Circolare ISVAP 474/D",
                       header_bg=C_BLUE)

    # -- SHEET REGOLAMENTO -----------------------------------------------------
    if results_reg:
        ws_reg = wb.create_sheet("Verifica_Regolamento")
        _write_check_sheet(ws_reg, results_reg,
                           "Verifica limiti — Regolamento fondo",
                           header_bg=C_BLUE)

    # -- DETTAGLIO EMITTENTI ---------------------------------------------------
    if "denominazione_emittente" in df_portafoglio.columns and col_val in df_portafoglio.columns:
        ws_emit = wb.create_sheet("Dettaglio_Emittenti")
        _write_dettaglio_sheet(ws_emit, df_portafoglio,
                               "Concentrazione per emittente",
                               "denominazione_emittente", col_val, tot)

    # -- DETTAGLIO GRUPPI ------------------------------------------------------
    if "gruppo_emittente" in df_portafoglio.columns and col_val in df_portafoglio.columns:
        ws_grp = wb.create_sheet("Dettaglio_Gruppi")
        _write_dettaglio_sheet(ws_grp, df_portafoglio,
                               "Concentrazione per gruppo emittente",
                               "gruppo_emittente", col_val, tot)

    # -- DB GREZZO -------------------------------------------------------------
    ws_db = wb.create_sheet("DB_Grezzo")
    # Mostra solo colonne rilevanti per non appesantire
    cols_show = [c for c in df_portafoglio.columns
                 if c not in ("escluso_calcolo",)]
    _write_db_sheet(ws_db, df_portafoglio[cols_show].head(2000))

    # -- LIMITI REGOLAMENTO RAW ------------------------------------------------
    if limiti_regolamento:
        ws_lim = wb.create_sheet("Limiti_Regolamento_Raw")
        _kpmg_logo(ws_lim, "Limiti estratti dal regolamento (Claude AI)")
        df_lim = pd.DataFrame(limiti_regolamento)
        for j, h in enumerate(df_lim.columns, 2):
            _header_cell(ws_lim, 5, j, str(h))
        for i, row in enumerate(df_lim.itertuples(index=False), 6):
            for j, val in enumerate(row, 2):
                _data_cell(ws_lim, i, j, val, stripe=(i % 2 == 0))
        _auto_width(ws_lim)

    # -- LEGENDA ---------------------------------------------------------------
    ws_leg = wb.create_sheet("Legenda")
    _write_legend_sheet(ws_leg)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

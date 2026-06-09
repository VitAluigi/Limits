"""
Genera l'Excel di output con:
- Sheet "DB_Grezzo": portafoglio filtrato originale
- Sheet "Analisi_Categorie": composizione per categoria
- Sheet "Analisi_Emittenti": concentrazione emittenti
- Sheet "Analisi_Paesi": esposizione per paese
- Sheet "Analisi_Valute": esposizione per valuta
- Sheet "Verifica_Limiti_Reg38": check Regolamento n.38
- Sheet "Verifica_Limiti_Regolamento": check regolamento gestione
- Sheet "Limiti_Reg38_Raw": limiti estratti da Reg.38
- Sheet "Limiti_Regolamento_Raw": limiti estratti dal regolamento
"""
import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
import datetime


# ── Colori ──────────────────────────────────────────────────────────────────
C_HEADER_DARK  = "1F3864"   # Blu scuro
C_HEADER_MED   = "2E75B6"   # Blu medio
C_HEADER_LIGHT = "BDD7EE"   # Azzurro chiaro
C_OK           = "C6EFCE"   # Verde chiaro
C_WARN         = "FFEB9C"   # Giallo
C_ERR          = "FFC7CE"   # Rosso chiaro
C_STRIPE       = "F2F2F2"   # Grigio righe alternate
C_WHITE        = "FFFFFF"
C_BORDER       = "BFBFBF"


def _thin_border():
    s = Side(style="thin", color=C_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)


def _header_cell(cell, text, bg=C_HEADER_DARK, fg="FFFFFF", bold=True, size=10):
    cell.value = text
    cell.font = Font(name="Arial", bold=bold, color=fg, size=size)
    cell.fill = PatternFill("solid", start_color=bg)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = _thin_border()


def _data_cell(cell, value, fmt=None, bold=False, bg=None, fg="000000"):
    cell.value = value
    cell.font = Font(name="Arial", size=9, bold=bold, color=fg)
    cell.alignment = Alignment(vertical="center")
    cell.border = _thin_border()
    if bg:
        cell.fill = PatternFill("solid", start_color=bg)
    if fmt:
        cell.number_format = fmt


def _auto_width(ws, min_w=8, max_w=50):
    for col in ws.columns:
        width = min_w
        for cell in col:
            if cell.value:
                width = max(width, min(len(str(cell.value)) + 2, max_w))
        ws.column_dimensions[get_column_letter(col[0].column)].width = width


def _write_df_sheet(ws, df: pd.DataFrame, title: str, header_bg=C_HEADER_MED):
    """Scrive un DataFrame su un foglio con header formattati."""
    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(df.columns), 1))
    t = ws.cell(1, 1, title)
    t.font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    t.fill = PatternFill("solid", start_color=C_HEADER_DARK)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 22

    # Header
    for j, col in enumerate(df.columns, 1):
        _header_cell(ws.cell(2, j), col, bg=header_bg)
    ws.row_dimensions[2].height = 30

    # Data
    for i, row in enumerate(df.itertuples(index=False), 3):
        bg = C_STRIPE if i % 2 == 0 else C_WHITE
        for j, val in enumerate(row, 1):
            col_name = df.columns[j - 1]
            fmt = None
            if "pct" in col_name.lower() or "%" in col_name:
                fmt = '0.00"%"'
            elif "valore" in col_name.lower():
                fmt = '#,##0.00'
            _data_cell(ws.cell(i, j), val, fmt=fmt, bg=bg)

    _auto_width(ws)


def _write_verifica_sheet(ws, df: pd.DataFrame, title: str):
    """Sheet verifica limiti con semaforo colorato."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
    t = ws.cell(1, 1, title)
    t.font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    t.fill = PatternFill("solid", start_color=C_HEADER_DARK)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 22

    for j, col in enumerate(df.columns, 1):
        _header_cell(ws.cell(2, j), col, bg=C_HEADER_MED)
    ws.row_dimensions[2].height = 30

    ESITO_COLOR = {
        "✅ OK": C_OK,
        "❌ SFORAMENTO MAX": C_ERR,
        "❌ SFORAMENTO EMITTENTE": C_ERR,
        "⚠️ SOTTO MINIMO": C_WARN,
        "⬜ NON RILEVABILE": C_STRIPE,
    }

    esito_col = list(df.columns).index("esito") + 1 if "esito" in df.columns else None

    for i, row in enumerate(df.itertuples(index=False), 3):
        esito_val = getattr(row, "esito", "")
        row_bg = ESITO_COLOR.get(esito_val, C_WHITE)
        for j, val in enumerate(row, 1):
            col_name = df.columns[j - 1]
            fmt = None
            if "pct" in col_name.lower():
                fmt = '0.00"%"'
            _data_cell(ws.cell(i, j), val, fmt=fmt, bg=row_bg)

    _auto_width(ws)


def genera_excel(
    df_portafoglio: pd.DataFrame,
    df_cat: pd.DataFrame,
    df_emit: pd.DataFrame,
    df_paesi: pd.DataFrame,
    df_valute: pd.DataFrame,
    df_verifica_reg38: pd.DataFrame,
    df_verifica_reg: pd.DataFrame,
    limiti_reg38: list[dict],
    limiti_regolamento: list[dict],
    nome_gestione: str,
    info_gestione: dict,
) -> bytes:
    """Genera l'Excel completo e restituisce bytes."""
    wb = Workbook()
    
    # ── 0. Cover ─────────────────────────────────────────────────────────────
    ws_cover = wb.active
    ws_cover.title = "Cover"
    ws_cover.sheet_view.showGridLines = False
    
    ws_cover.merge_cells("B2:H2")
    t = ws_cover["B2"]
    t.value = "ANALISI LIMITI DI INVESTIMENTO"
    t.font = Font(name="Arial", bold=True, size=16, color="FFFFFF")
    t.fill = PatternFill("solid", start_color=C_HEADER_DARK)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws_cover.row_dimensions[2].height = 36
    
    ws_cover.merge_cells("B3:H3")
    s = ws_cover["B3"]
    s.value = nome_gestione
    s.font = Font(name="Arial", bold=True, size=13, color="FFFFFF")
    s.fill = PatternFill("solid", start_color=C_HEADER_MED)
    s.alignment = Alignment(horizontal="center", vertical="center")
    ws_cover.row_dimensions[3].height = 28
    
    meta = [
        ("Gestione / Fondo", info_gestione.get("nome_gestione", nome_gestione)),
        ("Tipo", info_gestione.get("tipo", "—")),
        ("Compagnia", info_gestione.get("compagnia", "—")),
        ("Data elaborazione", datetime.date.today().strftime("%d/%m/%Y")),
        ("N. posizioni", len(df_portafoglio)),
        ("Totale portafoglio", f"{df_portafoglio['valore_mercato'].sum() if 'valore_mercato' in df_portafoglio.columns else 0:,.2f}"),
    ]
    for r, (label, val) in enumerate(meta, 5):
        ws_cover[f"B{r}"].value = label
        ws_cover[f"B{r}"].font = Font(name="Arial", bold=True, size=10)
        ws_cover[f"C{r}"].value = val
        ws_cover[f"C{r}"].font = Font(name="Arial", size=10)
        ws_cover.row_dimensions[r].height = 18
    
    ws_cover.column_dimensions["A"].width = 3
    ws_cover.column_dimensions["B"].width = 28
    ws_cover.column_dimensions["C"].width = 40

    # ── 1. DB Grezzo ──────────────────────────────────────────────────────────
    ws_db = wb.create_sheet("DB_Grezzo")
    _write_df_sheet(ws_db, df_portafoglio, f"DB GREZZO — {nome_gestione}", C_HEADER_MED)

    # ── 2. Analisi Categorie ──────────────────────────────────────────────────
    if not df_cat.empty:
        ws_cat = wb.create_sheet("Analisi_Categorie")
        _write_df_sheet(ws_cat, df_cat, "COMPOSIZIONE PER CATEGORIA IVASS", C_HEADER_MED)

    # ── 3. Analisi Emittenti ─────────────────────────────────────────────────
    if not df_emit.empty:
        ws_emit = wb.create_sheet("Analisi_Emittenti")
        _write_df_sheet(ws_emit, df_emit, "CONCENTRAZIONE PER EMITTENTE", C_HEADER_MED)

    # ── 4. Analisi Paesi ─────────────────────────────────────────────────────
    if not df_paesi.empty:
        ws_paesi = wb.create_sheet("Analisi_Paesi")
        _write_df_sheet(ws_paesi, df_paesi, "ESPOSIZIONE PER PAESE", C_HEADER_MED)

    # ── 5. Analisi Valute ────────────────────────────────────────────────────
    if not df_valute.empty:
        ws_val = wb.create_sheet("Analisi_Valute")
        _write_df_sheet(ws_val, df_valute, "ESPOSIZIONE PER VALUTA", C_HEADER_MED)

    # ── 6. Verifica Limiti Reg.38 ─────────────────────────────────────────────
    if not df_verifica_reg38.empty:
        ws_v38 = wb.create_sheet("Verifica_Reg38")
        _write_verifica_sheet(ws_v38, df_verifica_reg38, "VERIFICA LIMITI — REG. IVASS N.38")

    # ── 7. Verifica Limiti Regolamento Gestione ───────────────────────────────
    if not df_verifica_reg.empty:
        ws_vreg = wb.create_sheet("Verifica_Regolamento")
        _write_verifica_sheet(ws_vreg, df_verifica_reg, "VERIFICA LIMITI — REGOLAMENTO GESTIONE")

    # ── 8. Limiti Raw ─────────────────────────────────────────────────────────
    if limiti_reg38:
        ws_lr38 = wb.create_sheet("Limiti_Reg38_Raw")
        df_lr38 = pd.DataFrame(limiti_reg38)
        _write_df_sheet(ws_lr38, df_lr38, "LIMITI ESTRATTI — REG. IVASS N.38", C_HEADER_LIGHT)

    if limiti_regolamento:
        ws_lreg = wb.create_sheet("Limiti_Regolamento_Raw")
        df_lreg = pd.DataFrame(limiti_regolamento)
        _write_df_sheet(ws_lreg, df_lreg, "LIMITI ESTRATTI — REGOLAMENTO GESTIONE", C_HEADER_LIGHT)

    # ── Output ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

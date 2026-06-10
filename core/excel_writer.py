"""
Genera l'Excel di output con:
- Sheet "DB_Grezzo": portafoglio filtrato originale
- Sheet "Analisi_Categorie": composizione per categoria
- Sheet "Analisi_Emittenti": concentrazione emittenti
- Sheet "Analisi_Paesi": esposizione per paese
- Sheet "Analisi_Valute": esposizione per valuta
- Sheet "Verifica_Reg38": check normativa IVASS
- Sheet "Verifica_Regolamento": check regolamento gestione
- Sheet "Limiti_Reg38_Raw": limiti estratti da normativa IVASS
- Sheet "Limiti_Regolamento_Raw": limiti estratti dal regolamento
"""
import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import datetime

# Palette colori
C_KPMG_BLUE    = "00338D"   # RGB(0, 51, 141)  — KPMG blu
C_KPMG_BLUE_LT = "4472C4"   # blu medio per DB_Grezzo
C_WHITE        = "FFFFFF"
C_BLACK        = "000000"
C_STRIPE       = "F2F2F2"
C_OK           = "C6EFCE"
C_WARN         = "FFEB9C"
C_ERR          = "FFC7CE"
C_BORDER       = "BFBFBF"

# Font names
F_LOGO   = "KPMG Logo"
F_BOLD   = "KPMG Bold"
F_BODY   = "Arial"
SZ_HEAD  = 14
SZ_BODY  = 8


def _thin_border():
    s = Side(style="thin", color=C_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)


def _kpmg_header(ws, sheet_title: str):
    """
    Scrive l'intestazione KPMG standard:
      B2 → "KPMG" in KPMG Logo 14 blu KPMG
      B3 → sheet_title in KPMG Bold 14 blu KPMG
    Nasconde griglia e imposta zoom 100%.
    """
    ws.sheet_view.showGridLines = False

    # B2 — logo KPMG
    c2 = ws["B2"]
    c2.value = "KPMG"
    c2.font = Font(name=F_LOGO, size=SZ_HEAD, bold=False, color=C_KPMG_BLUE)
    c2.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 20

    # B3 — titolo analisi
    c3 = ws["B3"]
    c3.value = sheet_title
    c3.font = Font(name=F_BOLD, size=SZ_HEAD, bold=True, color=C_KPMG_BLUE)
    c3.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[3].height = 20

    # riga 4 — spazio
    ws.row_dimensions[4].height = 6

    # colonna A — margine sinistro stretto
    ws.column_dimensions["A"].width = 2


def _table_header_row(ws, row_idx: int, columns, header_bg=C_KPMG_BLUE):
    """Scrive una riga di intestazione tabella KPMG: sfondo blu, font Arial 8 bianco."""
    ws.row_dimensions[row_idx].height = 19
    for j, col in enumerate(columns, 2):          # parte da colonna B
        cell = ws.cell(row_idx, j, str(col))
        cell.font      = Font(name=F_BODY, size=SZ_BODY, bold=True, color=C_WHITE)
        cell.fill      = PatternFill("solid", start_color=header_bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = _thin_border()


def _table_data_row(ws, row_idx: int, values, columns, stripe=False):
    """Scrive una riga dati tabella KPMG: font Arial 8 nero, altezza 12."""
    ws.row_dimensions[row_idx].height = 12
    bg = C_STRIPE if stripe else C_WHITE
    for j, (val, col_name) in enumerate(zip(values, columns), 2):
        cell = ws.cell(row_idx, j)
        cell.value     = val
        cell.font      = Font(name=F_BODY, size=SZ_BODY, color=C_BLACK)
        cell.alignment = Alignment(vertical="center")
        cell.border    = _thin_border()
        cell.fill      = PatternFill("solid", start_color=bg)
        # Formato numerico
        if any(k in col_name.lower() for k in ["pct", "%"]):
            cell.number_format = '0.00"%"'
        elif any(k in col_name.lower() for k in ["valore", "mercato", "bilancio",
                                                   "nominale", "acquisto", "rateo"]):
            cell.number_format = '#,##0.00'


def _auto_width(ws, start_col=2, min_w=8, max_w=45):
    for col in ws.iter_cols(min_col=start_col):
        width = min_w
        for cell in col:
            if cell.value:
                width = max(width, min(len(str(cell.value)) + 2, max_w))
        ws.column_dimensions[get_column_letter(col[0].column)].width = width


def _write_kpmg_sheet(ws, df: pd.DataFrame, sheet_title: str,
                      header_bg=C_KPMG_BLUE):
    """
    Scrive un DataFrame in formato KPMG:
      B2 = KPMG logo, B3 = titolo, tabella da B5.
    """
    _kpmg_header(ws, sheet_title)

    if df.empty:
        ws["B5"].value = "Nessun dato disponibile."
        ws["B5"].font  = Font(name=F_BODY, size=SZ_BODY, color=C_BLACK)
        return

    _table_header_row(ws, 5, df.columns, header_bg)

    for i, row in enumerate(df.itertuples(index=False), 6):
        _table_data_row(ws, i, list(row), list(df.columns), stripe=(i % 2 == 0))

    _auto_width(ws)


def _write_verifica_sheet(ws, df: pd.DataFrame, sheet_title: str):
    """
    Sheet di verifica limiti con semaforo colorato.
    Stessa struttura KPMG ma le righe dati cambiano colore in base all'esito.
    """
    _kpmg_header(ws, sheet_title)

    if df.empty:
        ws["B5"].value = "Nessun dato disponibile."
        ws["B5"].font  = Font(name=F_BODY, size=SZ_BODY, color=C_BLACK)
        return

    _table_header_row(ws, 5, df.columns)

    ESITO_BG = {
        "OK":                   C_OK,
        "SFORAMENTO MAX":       C_ERR,
        "SFORAMENTO EMITTENTE": C_ERR,
        "SOTTO MINIMO":         C_WARN,
        "NON RILEVABILE":       C_STRIPE,
    }

    for i, row in enumerate(df.itertuples(index=False), 6):
        esito = getattr(row, "esito", "")
        row_bg = ESITO_BG.get(esito, C_WHITE)
        ws.row_dimensions[i].height = 12
        for j, (val, col_name) in enumerate(zip(list(row), list(df.columns)), 2):
            cell = ws.cell(i, j)
            cell.value     = val
            cell.font      = Font(name=F_BODY, size=SZ_BODY, color=C_BLACK)
            cell.alignment = Alignment(vertical="center")
            cell.border    = _thin_border()
            cell.fill      = PatternFill("solid", start_color=row_bg)
            if "pct" in col_name.lower():
                cell.number_format = '0.00"%"'

    _auto_width(ws)


def _write_db_grezzo(ws, df: pd.DataFrame, nome_gestione: str):
    """
    DB Grezzo: unico sheet senza header KPMG — intestazione semplice blu scuro
    per permettere di gestire le molte colonne senza fronzoli.
    """
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2

    # Titolo riga 1
    ws.merge_cells(start_row=1, start_column=2,
                   end_row=1, end_column=max(len(df.columns) + 1, 3))
    t = ws.cell(1, 2, f"DB GREZZO — {nome_gestione}")
    t.font      = Font(name=F_BOLD, size=10, bold=True, color=C_WHITE)
    t.fill      = PatternFill("solid", start_color=C_KPMG_BLUE)
    t.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 18

    if df.empty:
        return

    # Intestazione colonne → riga 2
    _table_header_row(ws, 2, df.columns)

    # Dati
    for i, row in enumerate(df.itertuples(index=False), 3):
        _table_data_row(ws, i, list(row), list(df.columns), stripe=(i % 2 == 0))

    _auto_width(ws)

def genera_excel(
    df_portafoglio: pd.DataFrame,
    df_cat:         pd.DataFrame,
    df_emit:        pd.DataFrame,
    df_paesi:       pd.DataFrame,
    df_valute:      pd.DataFrame,
    df_verifica_reg38: pd.DataFrame,
    df_verifica_reg:   pd.DataFrame,
    limiti_reg38:      list,
    limiti_regolamento: list,
    nome_gestione:  str,
    info_gestione:  dict,
) -> bytes:
    """Genera l'Excel completo KPMG-styled e restituisce bytes."""

    wb = Workbook()

    # 0. Cover
    ws_cover = wb.active
    ws_cover.title = "Cover"
    ws_cover.sheet_view.showGridLines = False
    ws_cover.column_dimensions["A"].width = 2
    ws_cover.column_dimensions["B"].width = 30
    ws_cover.column_dimensions["C"].width = 45

    # B2 logo
    c2 = ws_cover["B2"]
    c2.value = "KPMG"
    c2.font  = Font(name=F_LOGO, size=18, color=C_KPMG_BLUE)
    c2.alignment = Alignment(horizontal="left", vertical="center")
    ws_cover.row_dimensions[2].height = 26

    # B3 titolo
    c3 = ws_cover["B3"]
    c3.value = "Analisi Limiti di Investimento"
    c3.font  = Font(name=F_BOLD, size=14, bold=True, color=C_KPMG_BLUE)
    c3.alignment = Alignment(horizontal="left", vertical="center")
    ws_cover.row_dimensions[3].height = 22

    # B4 sottotitolo gestione
    c4 = ws_cover["B4"]
    c4.value = nome_gestione
    c4.font  = Font(name=F_BODY, size=11, color=C_KPMG_BLUE)
    c4.alignment = Alignment(horizontal="left", vertical="center")
    ws_cover.row_dimensions[4].height = 18

    ws_cover.row_dimensions[5].height = 10  # spazio

    meta = [
        ("Gestione / Fondo",   info_gestione.get("nome_gestione", nome_gestione)),
        ("Tipo",               info_gestione.get("tipo", "—")),
        ("Compagnia",          info_gestione.get("compagnia", "—")),
        ("Data elaborazione",  datetime.date.today().strftime("%d/%m/%Y")),
        ("N. posizioni",       len(df_portafoglio)),
        ("Totale portafoglio (EUR)",
         f"{df_portafoglio['valore_mercato'].sum():,.2f}"
         if "valore_mercato" in df_portafoglio.columns else "—"),
    ]
    for r, (label, val) in enumerate(meta, 6):
        lbl = ws_cover.cell(r, 2, label)
        lbl.font      = Font(name=F_BODY, size=9, bold=True, color=C_BLACK)
        lbl.alignment = Alignment(vertical="center")
        vl = ws_cover.cell(r, 3, val)
        vl.font       = Font(name=F_BODY, size=9, color=C_BLACK)
        vl.alignment  = Alignment(vertical="center")
        ws_cover.row_dimensions[r].height = 16

    # 1. DB Grezzo
    ws_db = wb.create_sheet("DB_Grezzo")
    _write_db_grezzo(ws_db, df_portafoglio, nome_gestione)

    # 2. Analisi Categorie
    if not df_cat.empty:
        ws_cat = wb.create_sheet("Analisi_Categorie")
        _write_kpmg_sheet(ws_cat, df_cat, "Composizione per categoria IVASS / CIC")

    # 3. Analisi Emittenti
    if not df_emit.empty:
        ws_emit = wb.create_sheet("Analisi_Emittenti")
        _write_kpmg_sheet(ws_emit, df_emit, "Concentrazione per emittente")

    # 4. Analisi Paesi
    if not df_paesi.empty:
        ws_paesi = wb.create_sheet("Analisi_Paesi")
        _write_kpmg_sheet(ws_paesi, df_paesi, "Esposizione per paese")

    # 5. Analisi Valute
    if not df_valute.empty:
        ws_val = wb.create_sheet("Analisi_Valute")
        _write_kpmg_sheet(ws_val, df_valute, "Esposizione per valuta")

    # 6. Verifica Normativa IVASS
    if not df_verifica_reg38.empty:
        ws_v38 = wb.create_sheet("Verifica_Reg38")
        _write_verifica_sheet(ws_v38, df_verifica_reg38,
                              "Verifica limiti — Normativa IVASS")

    # 7. Verifica Regolamento Gestione
    if not df_verifica_reg.empty:
        ws_vreg = wb.create_sheet("Verifica_Regolamento")
        _write_verifica_sheet(ws_vreg, df_verifica_reg,
                              "Verifica limiti — Regolamento gestione")

    # 8. Limiti Raw
    if limiti_reg38:
        ws_lr38 = wb.create_sheet("Limiti_Reg38_Raw")
        _write_kpmg_sheet(ws_lr38, pd.DataFrame(limiti_reg38),
                          "Limiti estratti — Normativa IVASS")

    if limiti_regolamento:
        ws_lreg = wb.create_sheet("Limiti_Regolamento_Raw")
        _write_kpmg_sheet(ws_lreg, pd.DataFrame(limiti_regolamento),
                          "Limiti estratti — Regolamento gestione")

    # Output
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

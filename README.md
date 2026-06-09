# Limits
# Analisi Limiti Gestioni & Fondi Assicurativi

App Streamlit locale per la verifica dei limiti di investimento di **gestioni separate** e **fondi interni** assicurativi italiani rispetto a:

- **Regolamento IVASS n.38** (limiti normativi)
- **Regolamento specifico** della gestione/fondo (limiti contrattuali)

---

## Requisiti

- Python 3.10+
- Una `ANTHROPIC_API_KEY` valida

---

## Installazione

```bash
cd limiti_gestioni
pip install -r requirements.txt
```

---

## Avvio

```bash
# Imposta la chiave API Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Avvia l'app
streamlit run app.py
```

L'app si apre automaticamente su `http://localhost:8501`

---

## Flusso di utilizzo

1. **Sidebar → Step 1**: Carica il PDF del **regolamento della gestione/fondo**  
   → Clicca *"Estrai limiti regolamento"* → Claude AI analizza e struttura i limiti

2. **Sidebar → Step 2**: Carica il PDF del **Regolamento IVASS n.38**  
   → Clicca *"Estrai limiti Reg. 38"* → Claude AI estrae tutti i limiti quantitativi

3. **Sidebar → Step 3**: Carica il file **SHIP Excel** (portafoglio)  
   → Clicca *"Carica portafoglio"* → il DB viene parsato e indicizzato

4. **Main area**: Seleziona la **gestione da analizzare** dal dropdown

5. Clicca **"GENERA EXCEL"** → download del file di analisi

---

## Output Excel — Sheet generati

| Sheet | Contenuto |
|-------|-----------|
| `Cover` | Metadata gestione + data elaborazione |
| `DB_Grezzo` | Portafoglio SHIP filtrato per la gestione selezionata |
| `Analisi_Categorie` | Composizione % per categoria IVASS |
| `Analisi_Emittenti` | Concentrazione per singolo emittente |
| `Analisi_Paesi` | Esposizione per paese |
| `Analisi_Valute` | Esposizione per valuta |
| `Verifica_Reg38` | Semaforo ✅/❌/⚠️ limiti Reg. IVASS n.38 |
| `Verifica_Regolamento` | Semaforo ✅/❌/⚠️ limiti Regolamento Gestione |
| `Limiti_Reg38_Raw` | Tabella limiti estratti da Reg. n.38 |
| `Limiti_Regolamento_Raw` | Tabella limiti estratti dal Regolamento |

---

## Struttura progetto

```
limiti_gestioni/
├── app.py                    # App Streamlit principale
├── requirements.txt
├── README.md
└── core/
    ├── pdf_parser.py         # Estrazione testo da PDF (PyMuPDF)
    ├── claude_extractor.py   # Estrazione limiti via Claude API
    ├── ship_parser.py        # Parsing file SHIP Excel IVASS
    ├── analisi.py            # Motore di calcolo e verifica limiti
    └── excel_writer.py       # Generazione Excel formattato
```

---

## Note tecniche

- Il parsing SHIP è flessibile: gestisce intestazioni su righe multiple e variazioni nei nomi colonna
- Claude AI è usato **solo per l'estrazione dei limiti** dai PDF (non per il calcolo)
- L'analisi dei limiti usa match testuale sulle categorie: se la categoria nel portafoglio non corrisponde esattamente a quella estratta dal PDF, l'esito sarà "⬜ NON RILEVABILE" — verificare manualmente
- Per file SHIP molto grandi, il caricamento può richiedere qualche secondo

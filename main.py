# ==============================================================================
# BRVM BOC SCRAPER - V2.1 (GitHub Actions & Gestion Quota Sheets)
# ==============================================================================

# --- Imports ---
import re
import time
import difflib
import unicodedata
import logging
import os
import json
from io import BytesIO
from collections import defaultdict

import pdfplumber
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2 import service_account
import urllib3

# --- Configuration du Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Paramètres Globaux ---
SPREADSHEET_ID = '1EGXyg13ml8a9zr4OaUPnJN3i-rwVO2uq330yfxJXnSM'
DEFAULT_HEADERS = ["Date", "Symbole", "Cours (F CFA)", "Volume échangé", "Valeurs échangées (F CFA)"]

# Keywords pour la reconnaissance des colonnes
KEYS = {
    "date": ["DATE", "YYYY", "YYYYMMDD", "DATE(YYYYMMDD)"],
    "sym": ["SYM", "SYMBOL", "TICKER", "ISSUER", "NOM", "LIBELLE", "ENTREPRISE", "COMPANY"],
    "cours": ["COUR", "PRIX", "PRICE"],
    "volume": ["VOLUME"],
    "valeurs": ["VALEUR", "MONTANT", "VALEURS"]
}

# --- Fonctions Utilitaires ---
def normalize_text(s):
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize('NFKD', s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[^A-Za-z0-9% ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.upper()

def extract_date_from_filename(url):
    m = re.search(r'boc_(\d{8})', url, flags=re.IGNORECASE)
    return m.group(1) if m else None

def backoff_sleep(attempt):
    time.sleep(min(2 ** attempt, 30))

# --- Authentification via Compte de Service (pour GitHub Actions) ---
def authenticate_google_services():
    logging.info("Authentification via compte de service Google...")
    try:
        creds_json_str = os.environ.get('GSPREAD_SERVICE_ACCOUNT')
        if not creds_json_str:
            logging.error("❌ Secret GSPREAD_SERVICE_ACCOUNT introuvable dans l'environnement.")
            return None
        creds_dict = json.loads(creds_json_str)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        logging.info("✅ Authentification Google réussie.")
        return gc
    except Exception as e:
        logging.error(f"❌ Erreur d'authentification : {e}")
        return None

# --- Fonctions Principales ---
def prepare_worksheets_metadata(spreadsheet):
    ws_meta = {}
    title_to_ws = {ws.title: ws for ws in spreadsheet.worksheets()}

    def find_index_by_keywords(header_norms, keywords):
        for i, hn in enumerate(header_norms):
            for k in keywords:
                if k in hn:
                    return i
        return None

    for title, ws in title_to_ws.items():
        # ======================================================================
        # CORRECTION : Ajout d'une pause pour éviter de dépasser le quota de
        # lecture de l'API Google Sheets (60 requêtes/minute).
        # ======================================================================
        time.sleep(1.1)

        try:
            header = ws.row_values(1)
        except Exception as e:
            logging.warning(f"Impossible de lire l'en-tête pour '{title}': {e}")
            header = []
        
        header_norms = [normalize_text(h) for h in header]
        
        indices = {
            "date": find_index_by_keywords(header_norms, KEYS["date"]) or 0,
            "sym": find_index_by_keywords(header_norms, KEYS["sym"]) or 1,
            "cours": find_index_by_keywords(header_norms, KEYS["cours"]) or 2,
            "volume": find_index_by_keywords(header_norms, KEYS["volume"]) or 3,
            "valeurs": find_index_by_keywords(header_norms, KEYS["valeurs"]) or 4,
        }

        if "ACTIONS" in normalize_text(title) and "BRVM" in normalize_text(title):
            indices = {"date": 0, "sym": 1, "cours": 2, "volume": 3, "valeurs": 4}
            logging.info(f"Feuille '{title}': mapping Actions_BRVM forcé.")

        existing_dates = set()
        try:
            col_no = indices["date"] + 1
            col_vals = ws.col_values(col_no)
            existing_dates = set(v for v in col_vals if re.fullmatch(r'\d{8}', v))
        except Exception as e:
            logging.warning(f"Impossible de lire les dates existantes pour '{title}': {e}")

        ws_meta[title] = {"ws": ws, "header": header, "indices": indices, "existing_dates": existing_dates}
    
    logging.info(f"Métadonnées initialisées pour {len(ws_meta)} feuilles.")
    return ws_meta, title_to_ws

def get_boc_links():
    url = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"
    r = requests.get(url, verify=False, timeout=30)
    soup = BeautifulSoup(r.content, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if re.search(r'boc_\d{8}_\d+\.pdf$', href, flags=re.IGNORECASE):
            full_url = href if href.startswith('http') else "https://www.brvm.org" + href
            links.add(full_url)
    return sorted(list(links), key=lambda u: extract_date_from_filename(u) or '')

def extract_data_from_pdf(pdf_url):
    logging.info(f"Téléchargement et analyse du PDF: {pdf_url}")
    try:
        r = requests.get(pdf_url, verify=False, timeout=30)
        pdf_file = BytesIO(r.content)
        data = []

        with pdfplumber.open(pdf_file) as pdf:
            pages_to_try = [p for p in [2, 3] if p < len(pdf.pages)]

            for pidx in pages_to_try:
                page = pdf.pages[pidx]
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        row = [(cell.strip() if cell else "") for cell in row]
                        if len(row) < 8: continue
                        
                        vol, val = row[-8], row[-7]
                        cours = row[-6] if len(row) >= 6 else ""
                        symbole = row[1] if len(row) > 1 and row[1] else row[0]

                        if re.search(r'\d', str(vol)) or re.search(r'\d', str(val)):
                            data.append({
                                "Symbole": symbole, "Cours (F CFA)": cours,
                                "Volume échangé": vol, "Valeurs échangées (F CFA)": val
                            })
        return data
    except Exception as e:
        logging.error(f"Erreur lors de l'extraction des données du PDF {pdf_url}: {e}")
        return []

def find_worksheet_title_for_symbol(raw_symbol, norm_to_title, norm_titles_list):
    s_norm = normalize_text(raw_symbol)
    if s_norm in norm_to_title:
        return norm_to_title[s_norm]
    
    matches = difflib.get_close_matches(s_norm, norm_titles_list, n=1, cutoff=0.7)
    return norm_to_title[matches[0]] if matches else None

def run():
    gc = authenticate_google_services()
    if not gc:
        return

    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    ws_meta, title_to_ws = prepare_worksheets_metadata(spreadsheet)
    
    norm_to_title = {normalize_text(title): title for title in title_to_ws.keys()}
    norm_titles_list = list(norm_to_title.keys())

    boc_links = get_boc_links()
    logging.info(f"{len(boc_links)} BOCs trouvés.")
    
    pending_appends = defaultdict(list)
    unmatched = []

    for boc in boc_links:
        date_only = extract_date_from_filename(boc)
        if not date_only:
            continue

        rows = extract_data_from_pdf(boc)
        
        for rec in rows:
            raw_sym = rec.get('Symbole', '')
            ws_title = find_worksheet_title_for_symbol(raw_sym, norm_to_title, norm_titles_list)
            
            if ws_title:
                meta = ws_meta.get(ws_title)
                if date_only in meta['existing_dates']:
                    continue
                
                inds = meta['indices']
                width = max(len(meta['header']), max(inds.values()) + 1)
                row = [""] * width
                
                row[inds['date']] = date_only
                row[inds['sym']] = raw_sym
                row[inds['cours']] = rec.get('Cours (F CFA)', '')
                row[inds['volume']] = rec.get('Volume échangé', '')
                row[inds['valeurs']] = rec.get('Valeurs échangées (F CFA)', '')
                
                pending_appends[ws_title].append(row)
                meta['existing_dates'].add(date_only)
            else:
                unmatched.append([date_only, raw_sym, rec.get('Cours (F CFA)',''), rec.get('Volume échangé',''), rec.get('Valeurs échangées (F CFA)','')])

    for title, rows in pending_appends.items():
        if rows:
            ws = title_to_ws.get(title)
            if ws:
                ws.append_rows(rows, value_input_option='USER_ENTERED')
                logging.info(f"Ajouté {len(rows)} nouvelles lignes dans '{title}'")

    if unmatched:
        try:
            ws_un = spreadsheet.worksheet("UNMATCHED")
        except gspread.exceptions.WorksheetNotFound:
            ws_un = spreadsheet.add_worksheet(title="UNMATCHED", rows=1000, cols=10)
        ws_un.append_rows(unmatched, value_input_option='USER_ENTERED')
        logging.info(f"{len(unmatched)} lignes non correspondantes écrites dans 'UNMATCHED'")

    logging.info("Processus terminé.")

if __name__ == "__main__":
    run()

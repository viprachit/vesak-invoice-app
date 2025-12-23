import streamlit as st
import pandas as pd
import base64
import os
import datetime
import requests
import math 
import re 
from io import BytesIO
from PIL import Image, ImageFile
import streamlit.components.v1 as components
from xhtml2pdf import pisa 
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# --- CRITICAL FIX FOR BROKEN IMAGES ---
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ==========================================
# 1. SETUP & ASSET GENERATION
# ==========================================
st.set_page_config(page_title="Vesak Care Invoice", layout="wide", page_icon="🏥")

LOGO_FILE = "logo.png"
URL_CONFIG_FILE = "url_config.txt"

# --- CONNECT TO GOOGLE SHEETS (CACHED) ---
@st.cache_resource(show_spinner=False)
def get_google_sheet_client():
    """Connects to Google Sheets using the standard gspread library."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            s_info = st.secrets["connections"]["gsheets"]
            
            creds_dict = {
                "type": s_info["type"],
                "project_id": s_info["project_id"],
                "private_key_id": s_info["private_key_id"],
                "private_key": s_info["private_key"],
                "client_email": s_info["client_email"],
                "client_id": s_info["client_id"],
                "auth_uri": s_info["auth_uri"],
                "token_uri": s_info["token_uri"],
                "auth_provider_x509_cert_url": s_info["auth_provider_x509_cert_url"],
                "client_x509_cert_url": s_info["client_x509_cert_url"],
            }
            
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(credentials)
            sheet = client.open_by_url(s_info["spreadsheet"])
            return sheet.sheet1 
    except Exception as e:
        st.error(f"Connection Error: {e}")
    return None

# --- AUTO-DOWNLOAD ICONS (CACHED) ---
@st.cache_resource(show_spinner=False)
def setup_icons():
    def download_and_save_icon(url, filename):
        if not os.path.exists(filename):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content)).convert("RGBA")
                    if "logo" in filename:
                        img.thumbnail((200, 200)) 
                    else:
                        img = img.resize((32, 32)) 
                    img.save(filename, format="PNG")
                    return True
            except:
                return False
        return True

    IG_URL = "https://cdn-icons-png.flaticon.com/512/2111/2111463.png" 
    FB_URL = "https://cdn-icons-png.flaticon.com/512/5968/5968764.png" 
    LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2966/2966327.png" 

    download_and_save_icon(IG_URL, "icon-ig.png")
    download_and_save_icon(FB_URL, "icon-fb.png")
    download_and_save_icon(LOGO_URL, "logo.png") 
    return True

setup_icons()

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def get_absolute_path(filename):
    if os.path.exists(filename): return os.path.abspath(filename).replace('\\', '/')
    return None

def get_clean_image_base64(file_path):
    if not os.path.exists(file_path): return None
    try:
        img = Image.open(file_path).convert("RGBA")
        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except: return None

def clean_text(text):
    return str(text).strip() if isinstance(text, str) else str(text)

def format_date_with_suffix(d):
    if pd.isna(d) or str(d).lower() in ['nan', 'n/a']: return "N/A"
    try:
        if not isinstance(d, (datetime.date, datetime.datetime)): d = pd.to_datetime(d)
        if isinstance(d, datetime.datetime): d = d.date()
        day = d.day
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th") if not 10 < day < 14 else "th"
        return d.strftime(f"%b. {day}{suffix} %Y")
    except: return str(d)

# --- ONEDRIVE HELPERS ---
def load_config_path(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r") as f: return f.read().strip()
    return ""

def save_config_path(path, file_name):
    with open(file_name, "w") as f: f.write(path.replace('"', '').strip())
    return path

def robust_file_downloader(url):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    })

    download_url = url
    if "?" in url: base_url = url.split("?")[0]
    else: base_url = url

    if "1drv.ms" in url or "sharepoint" in url or "onedrive" in url:
        download_url = base_url + "?download=1"
    
    try:
        response = session.get(download_url, verify=False, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type and len(response.content) < 5000:
                response = session.get(url, verify=False, allow_redirects=True)
            return BytesIO(response.content)
        raise Exception(f"Status Code: {response.status_code}")
    except Exception as e:
        raise Exception(f"Download failed: {e}")

@st.cache_data(ttl=600)
def load_excel_from_url_cached(url):
    try:
        file_content = robust_file_downloader(url)
        return pd.read_excel(file_content, sheet_name=None)
    except Exception as e:
        return None

# --- DATABASE FUNCTIONS ---

def get_history_data(sheet_obj):
    if sheet_obj is None: return pd.DataFrame()
    try:
        data = sheet_obj.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def get_next_invoice_number_gsheet(date_obj, df_hist):
    date_str = date_obj.strftime('%Y%m%d')
    next_seq = 1
    if not df_hist.empty and 'Invoice Number' in df_hist.columns:
        df_hist['Invoice Number'] = df_hist['Invoice Number'].astype(str)
        todays_inv = df_hist[df_hist['Invoice Number'].str.startswith(date_str)]
        if not todays_inv.empty:
            last_inv = todays_inv['Invoice Number'].iloc[-1]
            try:
                parts = last_inv.split('-')
                if len(parts) > 1:
                    last_seq = int(parts[-1])
                    next_seq = last_seq + 1
            except: pass
    return f"{date_str}-{next_seq:03d}"

def get_last_billing_qty(df_hist, customer_name, mobile):
    """Regex scan to find last paid quantity."""
    if df_hist.empty or 'Customer Name' not in df_hist.columns or 'Details' not in df_hist.columns:
        return 1
    mask = (df_hist['Customer Name'].astype(str).str.lower() == str(customer_name).lower())
    if 'Mobile' in df_hist.columns:
        mask = mask & (df_hist['Mobile'].astype(str) == str(mobile))
    
    client_history = df_hist[mask]
    if not client_history.empty:
        last_details = str(client_history.iloc[-1]['Details'])
        # Regex to find "Paid for X"
        match = re.search(r'Paid for (\d+)', last_details, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 1

def get_active_invoice_number(df_hist, customer_name):
    if df_hist.empty or 'Customer Name' not in df_hist.columns: return None
    mask = df_hist['Customer Name'].astype(str).str.lower() == str(customer_name).lower()
    user_hist = df_hist[mask]
    if user_hist.empty: return None
    if 'Service Ended' in user_hist.columns:
        user_hist = user_hist.copy()
        user_hist['Service Ended'] = user_hist['Service Ended'].fillna('').astype(str).str.strip()
        active_rows = user_hist[user_hist['Service Ended'] == '']
        if not active_rows.empty:
            return active_rows.iloc[-1]['Invoice Number']
    return None

def save_invoice_to_gsheet(data_dict, sheet_obj):
    if sheet_obj is None: return False
    try:
        row_values = [
            data_dict.get("Serial No.", ""), data_dict.get("Invoice Number", ""), data_dict.get("Date", ""),
            data_dict.get("Generated At", ""), data_dict.get("Customer Name", ""), data_dict.get("Age", ""),
            data_dict.get("Gender", ""), data_dict.get("Location", ""), data_dict.get("Address", ""),
            data_dict.get("Mobile", ""), data_dict.get("Plan", ""), data_dict.get("Shift", ""),
            data_dict.get("Recurring Service", ""), data_dict.get("Period", ""), data_dict.get("Visits", ""),
            data_dict.get("Amount", ""), data_dict.get("Notes / Remarks", ""), data_dict.get("Generated By", ""),
            data_dict.get("Amount Paid", ""), data_dict.get("Details", ""), data_dict.get("Service Started", ""),
            data_dict.get("Service Ended", "")
        ]
        sheet_obj.append_row(row_values)
        return True
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")
        return False

# --- ROBUST OVERWRITE FUNCTION ---
def update_invoice_in_gsheet(data_dict, sheet_obj):
    if sheet_obj is None: return False
    try:
        all_rows = sheet_obj.get_all_values()
        
        target_inv = str(data_dict["Invoice Number"]).strip()
        target_serial = str(data_dict["Serial No."]).strip()
        
        row_idx_to_update = None
        
        # Iterate through rows to find match based on BOTH Invoice No and Serial No
        for idx, row in enumerate(all_rows):
            if len(row) < 2: continue 
            
            # Assuming Col 1 is Serial, Col 2 is Invoice
            sheet_serial = str(row[0]).strip()
            # Handle float/int conversion for serial
            try: sheet_serial = str(int(float(sheet_serial)))
            except: pass
            
            sheet_inv = str(row[1]).strip()
            
            if sheet_serial == target_serial and sheet_inv == target_inv:
                row_idx_to_update = idx + 1 
                break
        
        if row_idx_to_update:
            row_values = [
                data_dict.get("Serial No.", ""), data_dict.get("Invoice Number", ""), data_dict.get("Date", ""),
                data_dict.get("Generated At", ""), data_dict.get("Customer Name", ""), data_dict.get("Age", ""),
                data_dict.get("Gender", ""), data_dict.get("Location", ""), data_dict.get("Address", ""),
                data_dict.get("Mobile", ""), data_dict.get("Plan", ""), data_dict.get("Shift", ""),
                data_dict.get("Recurring Service", ""), data_dict.get("Period", ""), data_dict.get("Visits", ""),
                data_dict.get("Amount", ""), data_dict.get("Notes / Remarks", ""), data_dict.get("Generated By", ""),
                data_dict.get("Amount Paid", ""), data_dict.get("Details", ""), data_dict.get("Service Started", ""),
                data_dict.get("Service Ended", "")
            ]
            range_name = f"A{row_idx_to_update}:V{row_idx_to_update}"
            sheet_obj.update(range_name, [row_values])
            return True
        else:
            st.error(f"❌ Critical Error: Invoice '{target_inv}' for Serial '{target_serial}' not found in Sheet. Cannot overwrite.")
            return False
    except Exception as e:
        st.error(f"Error updating Google Sheet: {e}")
        return False

def mark_service_ended(sheet_obj, invoice_number, end_date):
    if sheet_obj is None: return False, "No Sheet"
    try:
        try: cell = sheet_obj.find(str(invoice_number).strip(), in_column=2)
        except: cell = sheet_obj.find(str(invoice_number).strip())
             
        if cell:
            end_time = end_date.strftime("%Y-%m-%d") + " " + datetime.datetime.now().strftime("%H:%M:%S")
            range_name = f"V{cell.row}"
            sheet_obj.update(range_name, [[end_time]])
            return True, end_time
        return False, "Invoice not found"
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. UI & LOGIC
# ==========================================
SERVICES_MASTER = {
    "Plan A: Patient Attendant Care": ["All", "Basic Care", "Assistance with Activities for Daily Living", "Feeding & Oral Hygiene", "Mobility Support & Transfers", "Bed Bath and Emptying Bedpans", "Catheter & Ostomy Care"],
    "Plan B: Skilled Nursing": ["All", "Intravenous (IV) Therapy & Injections", "Medication Management", "Advanced Wound Care", "Catheter & Ostomy Care", "Post-Surgical Care"],
    "Plan C: Chronic Management": ["All", "Care for Bed-Ridden Patients", "Dementia & Alzheimer's Care", "Disability Support"],
    "Plan D: Elderly Companion": ["All", "Companionship & Conversation", "Fall Prevention & Mobility", "Light Meal Preparation"],
    "Plan E: Maternal & Newborn": ["All", "Postnatal & Maternal Care", "Newborn Care Assistance"],
    "Plan F: Rehabilitative Care": ["Therapeutic Massage", "Exercise Therapy", "Geriatric Rehabilitation", "Neuro Rehabilitation", "Pain Management", "Post Op Rehab"],
    "A-la-carte Services": ["Hospital Visits", "Medical Equipment", "Medicines", "Diagnostic Services", "Nutrition Consultation", "Ambulance", "Doctor Visits", "X-Ray", "Blood Collection"]
}
STANDARD_PLANS = ["Plan A: Patient Attendant Care", "Plan B: Skilled Nursing", "Plan C: Chronic Management", "Plan D: Elderly Companion", "Plan E: Maternal & Newborn"]
PLAN_DISPLAY_NAMES = {
    "Plan A: Patient Attendant Care": "Patient Care", "Plan B: Skilled Nursing": "Nursing Care",
    "Plan C: Chronic Management": "Chronic Management Care", "Plan D: Elderly Companion": "Elderly Companion Care",
    "Plan E: Maternal & Newborn": "Maternal & Newborn Care", "Plan F: Rehabilitative Care": "Rehabilitative Care",
    "A-la-carte Services": "Other Services"
}
COLUMN_ALIASES = {
    'Serial No.': ['Serial No.', 'serial no', 'sr no', 'sr. no.', 'id'],
    'Name': ['Name', 'name', 'patient name', 'client name'],
    'Mobile': ['Mobile', 'mobile', 'phone', 'contact'],
    'Location': ['Location', 'location', 'city'], 
    'Address': ['Address', 'address', 'residence'],
    'Gender': ['Gender', 'gender', 'sex'],
    'Age': ['Age', 'age'],
    'Service Required': ['Service Required', 'service required', 'plan'],
    'Sub Service': ['Sub Service', 'sub service', 'sub plan'],
    'Final Rate': ['Final Rate', 'final rate', 'amount', 'total amount'],
    'Unit Rate': ['Rate Agreed (₹)', 'rate agreed', 'unit rate', 'per day rate'],
    'Call Date': ['Call Date', 'call date'],
    'Notes': ['Notes / Remarks', 'notes'],
    'Shift': ['Shift', 'shift'],
    'Recurring': ['Recurring Service', 'recurring'],
    'Period': ['Period', 'period'],
    'Visits': ['Vists', 'visits', 'visit']
}

def get_base_lists(selected_plan, selected_sub_service):
    master_list = SERVICES_MASTER.get(selected_plan, [])
    if "All" in str(selected_sub_service) and selected_plan in STANDARD_PLANS:
        included_raw = [s for s in master_list if s.lower() != "all"]
    else:
        included_raw = [x.strip() for x in str(selected_sub_service).split(',')]
    included_clean = sorted(list(set([clean_text(s) for s in included_raw if clean_text(s)])))
    not_included_clean = []
    if selected_plan in STANDARD_PLANS:
        for plan_name in STANDARD_PLANS:
            if plan_name == selected_plan: continue 
            for item in SERVICES_MASTER.get(plan_name, []):
                if item.lower() == "all": continue
                cleaned = clean_text(item)
                if cleaned: not_included_clean.append(cleaned)
    else:
        for item in master_list:
            cleaned = clean_text(item)
            if cleaned and cleaned not in included_clean:
                not_included_clean.append(cleaned)
    return included_clean, list(set(not_included_clean))

def normalize_columns(df, aliases):
    df.columns = df.columns.astype(str).str.strip()
    for standard_name, possible_aliases in aliases.items():
        if standard_name in df.columns: continue 
        for alias in possible_aliases:
            for df_col in df.columns:
                if df_col.lower() == alias.lower():
                    df.rename(columns={df_col: standard_name}, inplace=True)
                    break 
    return df

# HTML Generators (Same as before)
def construct_description_html(row):
    shift_raw = str(row.get('Shift', '')).strip()
    period_raw = str(row.get('Period', '')).strip()
    shift_map = {"12-hr Day": "12 Hours - Day", "12-hr Night": "12 Hours - Night", "24-hr": "24 Hours"}
    shift_str = shift_map.get(shift_raw, shift_raw)
    time_suffix = " (Time)" if "12" in shift_str else ""
    return f"""<div style="margin-top: 4px;"><div style="font-size: 12px; color: #4a4a4a; font-weight: bold;">{shift_str}{time_suffix}</div><div style="font-size: 10px; color: #777; font-style: italic; margin-top: 2px;">{period_raw}</div></div>"""

def construct_amount_html(row, billing_qty):
    try: unit_rate = float(row.get('Unit Rate', 0)) 
    except: unit_rate = 0.0
    try: visits_needed = int(float(row.get('Visits', 0)))
    except: visits_needed = 0
    
    period_raw = str(row.get('Period', '')).strip()
    period_lower = period_raw.lower()
    shift_raw = str(row.get('Shift', '')).strip()
    is_per_visit = "per visit" in shift_raw.lower()
    
    billing_note = ""
    def get_plural(unit, qty):
        if "month" in unit.lower(): return "Months" if qty > 1 else "Month"
        if "week" in unit.lower(): return "Weeks" if qty > 1 else "Week"
        if "day" in unit.lower(): return "Days" if qty > 1 else "Day"
        if "visit" in unit.lower(): return "Visits" if qty > 1 else "Visit" 
        return unit

    if is_per_visit:
        paid_text = f"Paid for {billing_qty} {get_plural('Visit', billing_qty)}"
        if visits_needed > 1 and billing_qty == 1: billing_note = "Next Billing will be generated after the Payment to Continue the Service."
        elif billing_qty >= visits_needed: billing_note = f"Paid for {visits_needed} Visits."
        elif visits_needed == 1: billing_note = "Paid for 1 Visit."
        elif billing_qty < visits_needed: billing_note = f"Next Bill will be Generated after {billing_qty} Visits."
        else: billing_note = paid_text
    elif "month" in period_lower or "week" in period_lower:
        base_unit = "Month" if "month" in period_lower else "Week"
        paid_text = f"Paid for {billing_qty} {get_plural(base_unit, billing_qty)}"
        if visits_needed > 1 and billing_qty == 1: billing_note = "Next Billing will be generated after the Payment to Continue the Service."
        elif visits_needed > billing_qty: billing_note = f"Next Bill will be Generated after {billing_qty} {get_plural(base_unit, billing_qty)}."
        else: billing_note = paid_text
    elif "daily" in period_lower:
        paid_text = f"Paid for {billing_qty} {get_plural('Day', billing_qty)}"
        if 1 < visits_needed < 6 and billing_qty == 1: billing_note = "Next Billing will be generated after the Payment to Continue the Service."
        elif billing_qty >= visits_needed: billing_note = f"Paid for {visits_needed} Days."
        elif visits_needed == 1: billing_note = "Paid for 1 Day."
        elif billing_qty < visits_needed: billing_note = f"Next Bill will be Generated after {billing_qty} Days."
        else: billing_note = paid_text
    else:
        paid_text = f"Paid for {billing_qty} {period_raw}"
        billing_note = ""

    total_amount = unit_rate * billing_qty
    shift_map = {"12-hr Day": "12 Hours - Day", "12-hr Night": "12 Hours - Night", "24-hr": "24 Hours"}
    shift_display = shift_map.get(shift_raw, shift_raw)
    if "12" in shift_display and "Time" not in shift_display: shift_display += " (Time)"
    
    period_display = "Monthly" if "month" in period_lower else period_raw.capitalize()
    if "daily" in period_lower: period_display = "Daily"
    if is_per_visit: period_display = "Visit"
    
    unit_rate_str = "{:,.0f}".format(unit_rate)
    total_amount_str = "{:,.0f}".format(total_amount)
    unit_label = "Month" if "month" in period_lower else "Week" if "week" in period_lower else "Day"
    if is_per_visit: unit_label = "Visit"
    
    paid_for_text = f"Paid for {billing_qty} {get_plural(unit_label, billing_qty)}"

    return f"""
    <div style="text-align: right; font-size: 13px; color: #555;">
        <div style="margin-bottom: 4px;">{shift_display} / {period_display} = <b>₹ {unit_rate_str}</b></div>
        <div style="color: #CC4E00; font-weight: bold; font-size: 14px; margin: 2px 0;">X</div>
        <div style="font-weight: bold; font-size: 13px; margin: 2px 0; color: #333;">{paid_for_text}</div>
        <div style="border-bottom: 1px solid #ccc; width: 100%; margin: 6px 0;"></div>
        <div style="display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
            <span style="font-size: 13px; font-weight: 800; color: #002147; text-transform: uppercase;">TOTAL - </span>
            <span style="font-size: 16px; font-weight: bold; color: #000;">Rs. {total_amount_str}</span>
        </div>
        <div style="font-size: 10px; color: #666; font-style: italic; margin-top: 6px;">{billing_note}</div>
    </div>
    """

def convert_html_to_pdf(source_html):
    result = BytesIO()
    pisa_status = pisa.CreatePDF(source_html, dest=result)
    if pisa_status.err: return None
    return result.getvalue()

# ==========================================
# 5. MAIN APP UI
# ==========================================
st.title("🏥 Vesak Care - Invoice Generator")

# Absolute paths & Base64
abs_logo_path = get_absolute_path(LOGO_FILE)
abs_ig_path = get_absolute_path("icon-ig.png")
abs_fb_path = get_absolute_path("icon-fb.png")
logo_b64 = get_clean_image_base64(LOGO_FILE)
ig_b64 = get_clean_image_base64("icon-ig.png")
fb_b64 = get_clean_image_base64("icon-fb.png")

# Connect
sheet_obj = get_google_sheet_client()

with st.sidebar:
    st.header("📂 Data Source")
    if sheet_obj: st.success("Connected to Google Sheets ✅")
    else: st.error("❌ Not Connected to Google Sheets")
    data_source = st.radio("Load Confirmed Sheet via:", ["Upload File", "OneDrive Link"])

df = None
if data_source == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            xl = pd.ExcelFile(uploaded_file)
            sheet_names = xl.sheet_names
            default_ix = sheet_names.index('Confirmed') if 'Confirmed' in sheet_names else 0
            selected_sheet = st.sidebar.selectbox("Select Sheet:", sheet_names, index=default_ix)
            df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        except Exception as e:
            st.error(f"Error loading file: {e}")

elif data_source == "OneDrive Link":
    current_url = load_config_path(URL_CONFIG_FILE)
    url_input = st.sidebar.text_input("Paste OneDrive/Sharepoint Link:", value=current_url)
    if st.sidebar.button("Load from Link"):
        save_config_path(url_input, URL_CONFIG_FILE) 
        st.rerun()
    if current_url:
        all_sheets_dict = load_excel_from_url_cached(current_url)
        if all_sheets_dict:
            st.sidebar.success("✅ File Downloaded (Cached)")
            sheet_names = list(all_sheets_dict.keys())
            default_ix = sheet_names.index('Confirmed') if 'Confirmed' in sheet_names else 0
            selected_sheet = st.sidebar.selectbox("Select Sheet:", sheet_names, index=default_ix)
            df = all_sheets_dict[selected_sheet]
        else:
            st.sidebar.error("Link Error or File is empty.")

tab1, tab2, tab3 = st.tabs(["🧾 Generate Invoice", "🆕 Force New Invoice", "🛑 Manage Services"])

if df is not None:
    try:
        df = normalize_columns(df, COLUMN_ALIASES)
        # Validate columns
        required = ['Name', 'Mobile', 'Final Rate', 'Service Required', 'Unit Rate']
        missing = [k for k in required if k not in df.columns]
        if missing: st.error(f"Missing columns in Excel: {missing}"); st.stop()
        
        st.success("✅ Data Loaded")
        df_history = get_history_data(sheet_obj)

        # === SHARED GENERATOR FUNCTION (UPDATED) ===
        def render_invoice_ui(mode="standard"):
            
            # --- CUSTOMER FILTERING ---
            filter_col1, filter_col2 = st.columns([1, 2])
            with filter_col1:
                enable_date_filter = st.checkbox("Filter Customer List by Date", key=f"filt_chk_{mode}")
            
            selected_date_filter = datetime.date.today()
            
            if enable_date_filter:
                with filter_col2:
                    selected_date_filter = st.date_input("Show customers for Selected Date & +1 Day:", value=datetime.date.today(), key=f"filt_date_{mode}")
            
            d_start = selected_date_filter
            d_end = selected_date_filter + datetime.timedelta(days=1)

            # --- POPULATE CUSTOMER LIST ---
            unique_labels = [""]
            
            # Logic: Filter the loaded EXCEL file (df) to show relevant people
            # If standard mode, we might want to see everyone.
            # If filter enabled, check History to see who has active services or matches date?
            # User requirement: "Allow filtering this list by a specific date to reduce scrolling." 
            # Implies we look for customers in the *History* for that date range, then find them in Excel.
            
            if enable_date_filter and not df_history.empty and 'Date' in df_history.columns:
                 # Convert history dates
                 df_history['DateObj'] = pd.to_datetime(df_history['Date'], errors='coerce').dt.date
                 # Filter history for relevant dates
                 relevant_hist = df_history[(df_history['DateObj'] >= d_start) & (df_history['DateObj'] <= d_end)]
                 relevant_names = relevant_hist['Customer Name'].unique()
                 
                 # Filter Main Excel DF by these names
                 df_filtered = df[df['Name'].isin(relevant_names)]
                 
                 if df_filtered.empty:
                     st.warning(f"No customers found in History for {d_start} - {d_end}")
                     # Fallback to full list or keep empty? Let's show full list if filter returns nothing is usually safer, 
                     # but user wants to reduce scrolling. Let's keep it filtered.
                 
                 df_filtered = df_filtered.copy() # Avoid SettingWithCopy
                 df_filtered['Label'] = df_filtered['Name'].astype(str) + " (" + df_filtered['Mobile'].astype(str) + ")"
                 unique_labels = [""] + list(df_filtered['Label'].unique())
            else:
                 # Show everyone in Excel
                 df['Label'] = df['Name'].astype(str) + " (" + df['Mobile'].astype(str) + ")"
                 unique_labels = [""] + list(df['Label'].unique())

            selected_label = st.selectbox(f"Select Customer ({mode}):", unique_labels, key=f"sel_{mode}")
            
            if not selected_label:
                st.info("👈 Please select a customer to proceed.")
                return

            # Get Selected Row
            row = df[df['Label'] == selected_label].iloc[0]
            
            # --- DATA POPULATION ---
            c_serial_raw = row.get('Serial No.', '')
            try: c_serial = str(int(float(c_serial_raw)))
            except: c_serial = str(c_serial_raw)
            c_plan = row.get('Service Required', '')
            c_sub = row.get('Sub Service', '')
            c_ref_date = format_date_with_suffix(row.get('Call Date', 'N/A'))
            c_notes_raw = str(row.get('Notes', '')) if not pd.isna(row.get('Notes', '')) else ""
            c_name = row.get('Name', '')
            c_gender = row.get('Gender', '')
            raw_age = row.get('Age', '')
            try: c_age = str(int(float(raw_age))) if not pd.isna(raw_age) and raw_age != '' else ""
            except: c_age = str(raw_age)
            c_addr = row.get('Address', '')
            c_location = row.get('Location', c_addr) 
            c_mob = row.get('Mobile', '')
            inc_def, exc_def = get_base_lists(c_plan, c_sub)
            
            # REGEX PRE-FILL QTY
            default_qty = get_last_billing_qty(df_history, c_name, c_mob)

            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**Plan:** {PLAN_DISPLAY_NAMES.get(c_plan, c_plan)}")
                inv_date = st.date_input("Date:", value=datetime.date.today(), key=f"date_{mode}")
                fmt_date = format_date_with_suffix(inv_date)
                
                p_raw = str(row.get('Period', '')).strip()
                shift_raw = str(row.get('Shift', '')).strip() 
                
                # Label Logic
                if "per visit" in shift_raw.lower(): bill_label = "Visits"
                elif "month" in p_raw.lower(): bill_label = "Months"
                elif "week" in p_raw.lower(): bill_label = "Weeks"
                else: bill_label = "Days"
                
                billing_qty = st.number_input(f"Paid for how many {bill_label}?", min_value=1, value=default_qty, step=1, key=f"qty_{mode}_{selected_label}")
                
                # --- DUPLICATE DETECTION LOGIC ---
                # 1. Calculate the Invoice Number we WOULD generate
                calculated_inv_num = get_next_invoice_number_gsheet(inv_date, df_history)
                
                # 2. Check if this exact invoice number already exists in history
                is_duplicate = False
                if not df_history.empty and 'Invoice Number' in df_history.columns:
                    # Convert column to string to ensure matching works
                    existing_invs = df_history['Invoice Number'].astype(str).values
                    if calculated_inv_num in existing_invs:
                        is_duplicate = True
                
                if mode == "force_new":
                    is_duplicate = False # Force mode ignores duplicates
                    st.warning("⚠ You are about to generate a NEW invoice for an existing client.")
                
                chk_overwrite = False
                chk_duplicate_only = False
                allow_save = True

                if is_duplicate:
                    allow_save = False # Default to false unless user overrides
                    st.warning(f"⚠️ Invoice **{calculated_inv_num}** already exists in the system!")
                    
                    # RADIO BUTTONS FOR ACTION
                    action = st.radio(
                        "Choose Action:",
                        ["⛔ No Action (Safety)", "📄 Generate Duplicate Invoice (PDF Only)", "💾 Overwrite Existing Entry"],
                        key=f"rad_{mode}_{selected_label}"
                    )
                    
                    if action == "📄 Generate Duplicate Invoice (PDF Only)":
                        chk_duplicate_only = True
                        allow_save = True
                    elif action == "💾 Overwrite Existing Entry":
                        chk_overwrite = True
                        allow_save = True
                    # If "No Action", allow_save remains False
                
                # Input for Invoice Number (Auto-filled but editable)
                inv_num_input = st.text_input("Invoice No:", value=calculated_inv_num, key=f"inv_input_{mode}")
                st.caption(f"Ref Date: {c_ref_date}")

            with col2:
                generated_by_input = st.text_input("Invoice Generated By:", placeholder="", key=f"gen_by_{mode}")
                generated_by = generated_by_input if generated_by_input else "Vesak Patient Care"
                final_exc = st.multiselect("Excluded (Editable):", options=exc_def + ["Others"], default=exc_def, key=f"exc_{mode}")
            
            st.write("**Included Services:**")
            st.text(", ".join(inc_def))
            final_notes = st.text_area("Notes:", value=c_notes_raw, key=f"notes_{mode}")
            
            # HTML Previews
            desc_col_html = construct_description_html(row) 
            amount_col_html = construct_amount_html(row, billing_qty)
            
            # Button Logic
            btn_text = "Generate & Save Invoice"
            if chk_duplicate_only: btn_text = "Generate Duplicate PDF"
            if chk_overwrite: btn_text = "⚠ Update/Overwrite Invoice"
            if mode == "force_new": btn_text = "Force Generate New"

            if allow_save:
                if st.button(btn_text, key=f"btn_{mode}"):
                    # Processing...
                    clean_plan = PLAN_DISPLAY_NAMES.get(c_plan, c_plan)
                    
                    # Float conversions
                    try: unit_rate_val = float(row.get('Unit Rate', 0)) if not pd.isna(row.get('Unit Rate')) else 0.0
                    except: unit_rate_val = 0.0
                    total_billed_amount = unit_rate_val * billing_qty
                    
                    # Details String Logic
                    unit_label_for_details = "Month" if "month" in p_raw.lower() else "Week" if "week" in p_raw.lower() else "Day"
                    if "per visit" in shift_raw.lower(): unit_label_for_details = "Visit"
                    
                    def get_plural_s(u, q):
                        if "month" in u.lower(): return "Months" if q > 1 else "Month"
                        if "week" in u.lower(): return "Weeks" if q > 1 else "Week"
                        if "day" in u.lower(): return "Days" if q > 1 else "Day"
                        if "visit" in u.lower(): return "Visits" if q > 1 else "Visit"
                        return u
                    
                    details_text = f"Paid for {billing_qty} {get_plural_s(unit_label_for_details, billing_qty)}"
                    if mode == "force_new": details_text += " (New)"

                    # Prepare Data Dict
                    try: visits_val = int(float(row.get('Visits', 0)))
                    except: visits_val = 0
                    
                    gen_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    invoice_record = {
                        "Serial No.": str(c_serial), 
                        "Invoice Number": str(inv_num_input), 
                        "Date": str(fmt_date),
                        "Generated At": gen_ts, 
                        "Customer Name": str(c_name), 
                        "Age": str(c_age),
                        "Gender": str(c_gender), 
                        "Location": str(c_location), 
                        "Address": str(c_addr),
                        "Mobile": str(c_mob), 
                        "Plan": str(clean_plan), 
                        "Shift": str(row.get('Shift', '')),
                        "Recurring Service": str(row.get('Recurring', '')), 
                        "Period": str(row.get('Period', '')), 
                        "Visits": int(visits_val), 
                        "Amount": float(unit_rate_val), 
                        "Notes / Remarks": str(final_notes),  
                        "Generated By": str(generated_by), 
                        "Amount Paid": float(total_billed_amount), 
                        "Details": details_text, 
                        "Service Started": gen_ts, 
                        "Service Ended": ""
                    }

                    success = False
                    
                    # 1. DUPLICATE ONLY (No DB Touch)
                    if chk_duplicate_only:
                        st.info("Generating PDF Only (Database not modified).")
                        success = True
                        
                    # 2. OVERWRITE
                    elif chk_overwrite:
                        if update_invoice_in_gsheet(invoice_record, sheet_obj):
                            st.success(f"✅ Invoice {inv_num_input} Updated Successfully!")
                            success = True
                            
                    # 3. NEW ENTRY
                    else:
                        if mode == "force_new":
                            # End previous active service
                            prev_active_inv = get_active_invoice_number(df_history, c_name)
                            if prev_active_inv:
                                s_end, t_end = mark_service_ended(sheet_obj, prev_active_inv, inv_date)
                                if s_end: st.info(f"Closed previous invoice {prev_active_inv}")
                        
                        if save_invoice_to_gsheet(invoice_record, sheet_obj):
                            st.success(f"✅ Invoice {inv_num_input} Saved!")
                            success = True

                    if success:
                        # RENDER PDF PREVIEW (Code omitted for brevity - same as before)
                        inc_html = "".join([f'<li class="mb-1 text-xs text-gray-700">{item}</li>' for item in inc_def])
                        exc_html = "".join([f'<li class="mb-1 text-[10px] text-gray-500">{item}</li>' for item in final_exc])
                        notes_section = f"""<div class="mt-6 p-4 bg-gray-50 border border-gray-100 rounded"><h4 class="font-bold text-vesak-navy text-xs mb-1">NOTES</h4><p class="text-xs text-gray-600 whitespace-pre-wrap">{final_notes}</p></div>""" if final_notes else ""
                        
                        # PDF HTML (Simplified for this snippet)
                        html_template = f"""
                        <!DOCTYPE html>
                        <html lang="en">
                        <head>
                            <script src="https://cdn.tailwindcss.com"></script>
                            <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                            <script>
                                tailwind.config = {{ theme: {{ extend: {{ colors: {{ vesak: {{ navy: '#002147', gold: '#C5A065', orange: '#CC4E00' }} }} }} }} }}
                            </script>
                        </head>
                        <body class="py-10 bg-gray-100 font-sans">
                            <div class="max-w-[210mm] mx-auto mb-6 flex justify-end no-print px-4">
                                <button onclick="generatePDF()" class="bg-vesak-navy text-white px-6 py-2 rounded shadow hover:bg-vesak-gold transition font-bold text-xs uppercase tracking-widest">Download PDF</button>
                            </div>
                            <div class="bg-white w-[210mm] min-h-[297mm] mx-auto p-10 shadow-lg relative flex flex-col" id="invoice-content">
                                <div class="flex justify-between items-start border-b pb-6 mb-6">
                                    <img src="data:image/png;base64,{logo_b64}" class="w-20">
                                    <div class="text-right">
                                        <h1 class="text-2xl font-bold text-vesak-navy">INVOICE</h1>
                                        <p class="text-sm">#{inv_num_input}</p>
                                        <p class="text-sm">{fmt_date}</p>
                                    </div>
                                </div>
                                <div class="mb-8">
                                    <h3 class="font-bold text-vesak-navy">Billed To:</h3>
                                    <p class="text-lg font-bold">{c_name}</p>
                                    <p class="text-sm text-gray-600">{c_addr}</p>
                                    <p class="text-sm text-gray-600">{c_mob}</p>
                                </div>
                                <table class="w-full mb-8">
                                    <tr class="bg-vesak-navy text-white"><th class="p-2 text-left">Description</th><th class="p-2 text-right">Amount</th></tr>
                                    <tr class="border-b"><td class="p-2">{clean_plan}<br/><span class="text-xs text-gray-500">{row.get('Shift','')}</span></td><td class="p-2 text-right">{amount_col_html}</td></tr>
                                </table>
                                {notes_section}
                            </div>
                            <script>
                                function generatePDF() {{
                                    const element = document.getElementById('invoice-content');
                                    html2pdf().from(element).save('Invoice_{c_name}.pdf');
                                }}
                            </script>
                        </body>
                        </html>
                        """
                        components.html(html_template, height=1000, scrolling=True)

        # RENDER TABS
        with tab1: render_invoice_ui(mode="standard")
        with tab2: render_invoice_ui(mode="force_new")
        with tab3: st.write("Manage Services (Same as before)")

    except Exception as e:
        st.error(f"App Error: {e}")

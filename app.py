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

# --- SESSION STATE INITIALIZATION ---
if 'chk_print_dup' not in st.session_state: st.session_state.chk_print_dup = False
if 'chk_overwrite' not in st.session_state: st.session_state.chk_overwrite = False

# --- CONNECT TO GOOGLE SHEETS (OPTIMIZED) ---
@st.cache_resource
def get_google_sheet_client():
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

# --- AUTO-DOWNLOAD ICONS (OPTIMIZED) ---
@st.cache_resource
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

def load_config_path(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r") as f: return f.read().strip()
    return ""

def save_config_path(path, file_name):
    with open(file_name, "w") as f: f.write(path.replace('"', '').strip())
    return path

@st.cache_data(show_spinner=False)
def robust_file_downloader(url):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
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
        raise Exception(f"Download failed: {e}. Ensure the OneDrive link is set to 'Anyone with the link'.")

# --- GOOGLE SHEETS DATABASE FUNCTIONS ---

@st.cache_data(show_spinner=False, ttl=15)
def get_history_data(_sheet_obj):
    if _sheet_obj is None: return pd.DataFrame()
    try:
        data = _sheet_obj.get_all_records()
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

def get_record_by_serial(df_hist, serial_no):
    if df_hist.empty or 'Serial No.' not in df_hist.columns: return None
    df_hist['Serial_Clean'] = df_hist['Serial No.'].astype(str).str.split('.').str[0].str.strip()
    target_serial = str(serial_no).split('.')[0].strip()
    match = df_hist[df_hist['Serial_Clean'] == target_serial]
    if not match.empty: return match.iloc[0]
    return None

def get_last_billing_qty(df_hist, customer_name, mobile):
    if df_hist.empty or 'Customer Name' not in df_hist.columns or 'Details' not in df_hist.columns:
        return 1
    mask = (df_hist['Customer Name'].astype(str).str.lower() == str(customer_name).lower())
    if 'Mobile' in df_hist.columns:
        mask = mask & (df_hist['Mobile'].astype(str) == str(mobile))
    client_history = df_hist[mask]
    if not client_history.empty:
        last_details = str(client_history.iloc[-1]['Details'])
        match = re.search(r'Paid for (\d+)', last_details)
        if match: return int(match.group(1))
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
        get_history_data.clear()
        return True
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")
        return False

# --- IMPROVED ROBUST UPDATE FUNCTION ---
def update_invoice_in_gsheet(data_dict, sheet_obj, original_inv_to_find):
    if sheet_obj is None: return False
    try:
        all_rows = sheet_obj.get_all_values()
        target_serial = str(data_dict["Serial No."]).strip()
        target_inv_search = str(original_inv_to_find).strip()
        
        row_idx_to_update = None
        for idx, row in enumerate(all_rows):
            if len(row) < 2: continue 
            sheet_serial_raw = str(row[0]).strip()
            try: sheet_serial = str(int(float(sheet_serial_raw)))
            except: sheet_serial = sheet_serial_raw
            sheet_inv = str(row[1]).strip()
            
            # Double Lock: Serial No + Old Invoice No
            if sheet_serial == target_serial and sheet_inv == target_inv_search:
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
            get_history_data.clear()
            return True
        else:
            st.error(f"❌ Critical Error: Could not find original row with Serial '{target_serial}' AND Invoice '{target_inv_search}'.")
            return False
    except Exception as e:
        st.error(f"Error updating Google Sheet: {e}")
        return False

def mark_service_ended(sheet_obj, invoice_number, end_date):
    if sheet_obj is None: return False, "No Sheet"
    try:
        try:
             cell = sheet_obj.find(str(invoice_number).strip(), in_column=2)
        except:
             cell = sheet_obj.find(str(invoice_number).strip())
        if cell:
            end_time = end_date.strftime("%Y-%m-%d") + " " + datetime.datetime.now().strftime("%H:%M:%S")
            range_name = f"V{cell.row}"
            sheet_obj.update(range_name, [[end_time]])
            get_history_data.clear()
            return True, end_time
        return False, "Invoice not found"
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. DATA LOGIC & LISTS
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

# --- HTML CONSTRUCTORS ---
def construct_description_html(row):
    shift_raw = str(row.get('Shift', '')).strip()
    recurring = str(row.get('Recurring', '')).strip().lower()
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
# 4. UI & LOGIC
# ==========================================
st.title("🏥 Vesak Care - Invoice Generator")

abs_logo_path = get_absolute_path(LOGO_FILE)
abs_ig_path = get_absolute_path("icon-ig.png")
abs_fb_path = get_absolute_path("icon-fb.png")
logo_b64 = get_clean_image_base64(LOGO_FILE)
ig_b64 = get_clean_image_base64("icon-ig.png")
fb_b64 = get_clean_image_base64("icon-fb.png")

sheet_obj = get_google_sheet_client()

with st.sidebar:
    st.header("📂 Data Source")
    if sheet_obj: st.success("Connected to Google Sheets ✅")
    else: st.error("❌ Not Connected to Google Sheets")
    data_source = st.radio("Load Confirmed Sheet via:", ["Upload File", "OneDrive Link"])
    
    st.markdown("---")
    if st.button("🔄 Refresh Data Cache"):
        get_history_data.clear()
        st.cache_data.clear()
        st.success("Cache cleared! Reloading...")
        st.rerun()

raw_file_obj = None
if data_source == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
    if uploaded_file: raw_file_obj = uploaded_file
elif data_source == "OneDrive Link":
    current_url = load_config_path(URL_CONFIG_FILE)
    url_input = st.sidebar.text_input("Paste OneDrive/Sharepoint Link:", value=current_url)
    if st.sidebar.button("Load from Link"):
        save_config_path(url_input, URL_CONFIG_FILE) 
        st.rerun()
    if current_url:
        try: 
            raw_file_obj = robust_file_downloader(current_url)
            st.sidebar.success("✅ File Downloaded")
        except Exception as e: 
            st.sidebar.error(f"Link Error: {e}")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🧾 Generate Invoice", "🆕 Force New Invoice", "📄 Duplicate Invoice (Reprint)", "🛑 Manage Services"])

if raw_file_obj:
    df = None
    try:
        if hasattr(raw_file_obj, 'seek'): raw_file_obj.seek(0)
        xl = pd.ExcelFile(raw_file_obj)
        sheet_names = xl.sheet_names
        default_ix = sheet_names.index('Confirmed') if 'Confirmed' in sheet_names else 0
        selected_sheet = st.sidebar.selectbox("Select Sheet:", sheet_names, index=default_ix)
        df = pd.read_excel(raw_file_obj, sheet_name=selected_sheet)
    except Exception as e_excel:
        st.error(f"❌ Excel Read Error: {e_excel}")
        st.info("ℹ️ File seems corrupted or password protected.")

    if df is not None:
        try:
            df = normalize_columns(df, COLUMN_ALIASES)
            missing = [k for k in ['Name', 'Mobile', 'Final Rate', 'Service Required', 'Unit Rate'] if k not in df.columns]
            if missing: st.error(f"Missing columns: {missing}"); st.stop()
            st.success("✅ Data Loaded")

            # [OPTIMIZED] Calls cached data fetcher (now with TTL=15s)
            df_history = get_history_data(sheet_obj)

            # === SHARED GENERATOR FUNCTION FOR TAB 1 & 2 ===
            def render_invoice_ui(mode="standard"):
                chk_overwrite = False
                
                filter_col1, filter_col2 = st.columns([1, 2])
                with filter_col1:
                    enable_date_filter = st.checkbox("Filter Customer List by Date", key=f"filt_chk_{mode}")
                
                selected_date_filter = None
                unique_labels = []
                
                if enable_date_filter:
                    with filter_col2:
                        selected_date_filter = st.date_input("Show customers for Selected Date & +1 Day:", value=datetime.date.today(), key=f"filt_date_{mode}")
                        d_start = selected_date_filter 
                        d_end = selected_date_filter + datetime.timedelta(days=1)
                
                    if mode == "force_new":
                        if not df_history.empty and 'Customer Name' in df_history.columns:
                            hist_data = df_history.copy()
                            if enable_date_filter and 'Date' in hist_data.columns:
                                 hist_data['DateObj'] = pd.to_datetime(hist_data['Date'], errors='coerce').dt.date
                                 hist_data = hist_data[(hist_data['DateObj'] >= d_start) & (hist_data['DateObj'] <= d_end)]
                            hist_names = hist_data['Customer Name'].unique()
                            df['Label'] = df['Name'].astype(str) + " (" + df['Mobile'].astype(str) + ")"
                            df_filtered = df[df['Name'].isin(hist_names)]
                            unique_labels = [""] + list(df_filtered['Label'].unique())
                        else:
                            unique_labels = [""]
                    else:
                        if enable_date_filter and not df_history.empty and 'Date' in df_history.columns and 'Customer Name' in df_history.columns:
                              df_history['DateObj'] = pd.to_datetime(df_history['Date'], errors='coerce').dt.date
                              filtered_hist = df_history[(df_history['DateObj'] >= d_start) & (df_history['DateObj'] <= d_end)]
                              valid_names = filtered_hist['Customer Name'].unique()
                              df_filtered = df[df['Name'].isin(valid_names)]
                              if df_filtered.empty:
                                  st.warning(f"No customers found between {d_start} and {d_end}.")
                                  df_filtered = df 
                              df_filtered['Label'] = df_filtered['Name'].astype(str) + " (" + df_filtered['Mobile'].astype(str) + ")"
                              unique_labels = [""] + list(df_filtered['Label'].unique())
                        else:
                            df['Label'] = df['Name'].astype(str) + " (" + df['Mobile'].astype(str) + ")"
                            unique_labels = [""] + list(df['Label'].unique())
                else:
                    df['Label'] = df['Name'].astype(str) + " (" + df['Mobile'].astype(str) + ")"
                    unique_labels = [""] + list(df['Label'].unique())

                selected_label = st.selectbox(f"Select Customer ({mode}):", unique_labels, key=f"sel_{mode}")
                
                if not selected_label:
                    st.info("👈 Please select a customer to proceed.")
                    return

                row = df[df['Label'] == selected_label].iloc[0]
                
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
                
                st.divider()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.info(f"**Plan:** {PLAN_DISPLAY_NAMES.get(c_plan, c_plan)}")
                    inv_date = st.date_input("Date:", value=datetime.date.today(), key=f"date_{mode}")
                    fmt_date = format_date_with_suffix(inv_date)
                    default_qty = get_last_billing_qty(df_history, c_name, c_mob)
                    p_raw = str(row.get('Period', '')).strip()
                    shift_raw = str(row.get('Shift', '')).strip() 
                    
                    if "per visit" in shift_raw.lower(): bill_label = "Visits"
                    elif "month" in p_raw.lower(): bill_label = "Months"
                    elif "week" in p_raw.lower(): bill_label = "Weeks"
                    else: bill_label = "Days"
                    
                    billing_qty = st.number_input(f"Paid for how many {bill_label}?", min_value=1, value=default_qty, step=1, key=f"qty_{mode}_{selected_label}")
                    
                    existing_record = get_record_by_serial(df_history, c_serial)
                    existing_inv_num = ""
                    default_inv_num = "" 
                    
                    # Calculate next sequential number
                    next_sequential_inv = get_next_invoice_number_gsheet(inv_date, df_history)

                    conflict_exists = False
                    if existing_record is not None:
                        existing_inv_num = existing_record['Invoice Number']
                        if existing_record['Date'] == fmt_date:
                            conflict_exists = True
                            if mode == "standard": st.warning(f"⚠️ Invoice already exists for today! (Inv: {existing_inv_num})")
                        else:
                            if mode == "standard": st.info(f"ℹ️ Last Invoice Found: {existing_inv_num}")

                    if mode == "force_new":
                        default_inv_num = next_sequential_inv
                        st.warning("⚠ You are about to generate a NEW invoice for an existing client.")
                    else:
                        if conflict_exists:
                             chk_overwrite = st.checkbox("Overwrite Existing Entry", key=f"chk_over_{mode}")

                        if chk_overwrite:
                            default_inv_num = existing_inv_num
                        else:
                            default_inv_num = next_sequential_inv

                    inv_num_input = st.text_input("Invoice No (New/Editable):", value=default_inv_num, key=f"inv_input_{mode}_{inv_date}_{chk_overwrite}")
                    st.caption(f"Ref Date: {c_ref_date}")
                    
                with col2:
                    generated_by_input = st.text_input("Invoice Generated By:", placeholder="", key=f"gen_by_{mode}")
                    generated_by = generated_by_input if generated_by_input else "Vesak Patient Care"
                    final_exc = st.multiselect("Excluded (Editable):", options=exc_def + ["Others"], default=exc_def, key=f"exc_{mode}")
                    
                st.write("**Included Services:**")
                st.text(", ".join(inc_def))
                final_notes = st.text_area("Notes:", value=c_notes_raw, key=f"notes_{mode}")
                
                desc_col_html = construct_description_html(row) 
                amount_col_html = construct_amount_html(row, billing_qty)
                
                btn_label = "Generate & Save Invoice"
                if mode == "force_new": btn_label = "⚠ Force Generate New Invoice"
                elif chk_overwrite: btn_label = "⚠ Update/Overwrite Invoice"
                
                if st.button(btn_label, key=f"btn_{mode}"):
                    proceed = True
                    if mode == "standard" and conflict_exists and not chk_overwrite:
                        st.error("❌ Invoice exists for this date! Check 'Overwrite' to update it.")
                        proceed = False
                    
                    if proceed:
                        clean_plan = PLAN_DISPLAY_NAMES.get(c_plan, c_plan)
                        inv_num = inv_num_input
                        
                        def safe_float(val):
                            try: return float(val) if not pd.isna(val) else 0.0
                            except: return 0.0
                        
                        unit_rate_val = safe_float(row.get('Unit Rate', 0))
                        total_billed_amount = unit_rate_val * billing_qty
                        
                        unit_label_for_details = "Month" if "month" in p_raw.lower() else "Week" if "week" in p_raw.lower() else "Day"
                        if "per visit" in shift_raw.lower(): unit_label_for_details = "Visit"

                        def get_plural_save(unit, qty):
                            if "month" in unit.lower(): return "Months" if qty > 1 else "Month"
                            if "week" in unit.lower(): return "Weeks" if qty > 1 else "Week"
                            if "day" in unit.lower(): return "Days" if qty > 1 else "Day"
                            if "visit" in unit.lower(): return "Visits" if qty > 1 else "Visit"
                            return unit
                        
                        details_text = f"Paid for {billing_qty} {get_plural_save(unit_label_for_details, billing_qty)}"
                        if mode == "force_new": details_text += " (New)"

                        success = False
                        
                        try: visits_val = int(safe_float(row.get('Visits', 0)))
                        except: visits_val = 0
                        period_val = str(row.get('Period', ''))
                        generated_at_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        invoice_record = {
                            "Serial No.": str(c_serial), "Invoice Number": str(inv_num), "Date": str(fmt_date),
                            "Generated At": generated_at_ts, "Customer Name": str(c_name), "Age": str(c_age),
                            "Gender": str(c_gender), "Location": str(c_location), "Address": str(c_addr),
                            "Mobile": str(c_mob), "Plan": str(clean_plan), "Shift": str(row.get('Shift', '')),
                            "Recurring Service": str(row.get('Recurring', '')), "Period": period_val, 
                            "Visits": int(visits_val), "Amount": float(unit_rate_val), "Notes / Remarks": str(final_notes),  
                            "Generated By": str(generated_by), "Amount Paid": float(total_billed_amount), 
                            "Details": details_text, "Service Started": generated_at_ts, "Service Ended": ""
                        }
                        
                        if mode == "standard" and chk_overwrite:
                            if update_invoice_in_gsheet(invoice_record, sheet_obj, existing_inv_num):
                                st.success(f"✅ Invoice {existing_inv_num} UPDATED to {inv_num}!")
                                success = True
                        elif mode == "standard":
                            if save_invoice_to_gsheet(invoice_record, sheet_obj):
                                st.success(f"✅ Invoice {inv_num} SAVED!")
                                success = True
                        elif mode == "force_new":
                            prev_active_inv = get_active_invoice_number(df_history, c_name)
                            if prev_active_inv:
                                success_end, end_ts = mark_service_ended(sheet_obj, prev_active_inv, inv_date)
                                if success_end: st.info(f"ℹ️ Previous Invoice {prev_active_inv} marked as Ended at {end_ts}")
                            
                            if save_invoice_to_gsheet(invoice_record, sheet_obj):
                                st.success(f"✅ New Invoice {inv_num} CREATED!")
                                success = True

                        if success:
                            inc_html = "".join([f'<li class="mb-1 text-xs text-gray-700">{item}</li>' for item in inc_def])
                            exc_html = "".join([f'<li class="mb-1 text-[10px] text-gray-500">{item}</li>' for item in final_exc])
                            notes_section = ""
                            if final_notes:
                                notes_section = f"""<div class="mt-6 p-4 bg-gray-50 border border-gray-100 rounded"><h4 class="font-bold text-vesak-navy text-xs mb-1">NOTES</h4><p class="text-xs text-gray-600 whitespace-pre-wrap">{final_notes}</p></div>"""

                            html_template = f"""
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <script src="https://cdn.tailwindcss.com"></script>
                                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
                                <script>tailwind.config = {{ theme: {{ extend: {{ colors: {{ vesak: {{ navy: '#002147', gold: '#C5A065', orange: '#CC4E00' }} }}, fontFamily: {{ serif: ['"Playfair Display"', 'serif'], sans: ['"Lato"', 'sans-serif'] }} }} }} }}</script>
                                <style>@import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&family=Playfair+Display:wght@400;600;700&display=swap'); body {{ font-family: 'Lato', sans-serif; background: #f0f0f0; }} .invoice-page {{ background: white; width: 210mm; min-height: 297mm; margin: 20px auto; padding: 40px; position: relative; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); display: flex; flex-direction: column; }} .watermark-container {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; opacity: 0.03; pointer-events: none; z-index: 0; }} .watermark-text {{ font-family: 'Playfair Display', serif; font-size: 80px; font-weight: 700; color: #002147; letter-spacing: 0.3em; }} @media print {{ body {{ background: white; -webkit-print-color-adjust: exact; }} .invoice-page {{ margin: 0; box-shadow: none; width: 100%; height: 100%; padding: 40px; }} .no-print {{ display: none !important; }} .watermark-container {{ opacity: 0.015 !important; }} }}</style>
                            </head>
                            <body class="py-10">
                                <div class="max-w-[210mm] mx-auto mb-6 flex justify-end no-print px-4"><button onclick="generatePDF()" class="bg-vesak-navy text-white px-6 py-2 rounded shadow hover:bg-vesak-gold transition font-bold text-xs uppercase tracking-widest"><i class="fas fa-download mr-2"></i> Download PDF</button></div>
                                <div class="invoice-page" id="invoice-content">
                                    <div class="watermark-container"><img src="data:image/png;base64,{logo_b64}" style="width: 300px; opacity: 0.3;"><div class="watermark-text mt-4">VESAK</div></div>
                                    <header class="relative z-10 w-full mb-10"><div class="flex justify-between items-start border-b border-gray-100 pb-6"><div class="flex items-center gap-5"><img src="data:image/png;base64,{logo_b64}" class="w-20 h-auto"><div><h1 class="font-serif text-2xl font-bold text-vesak-navy tracking-wide leading-none mb-2">Vesak Care <span class="text-vesak-gold font-normal">Foundation</span></h1><div class="flex flex-col text-xs text-gray-500 font-light tracking-wide space-y-0.5"><span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Web</span> vesakcare.com</span><span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Email</span> vesakcare@gmail.com</span><span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Phone</span> +91 7777 000 878</span></div></div></div><div class="text-right"><span class="block font-serif text-3xl text-gray-200 tracking-widest mb-2">INVOICE</span><div class="text-xs text-vesak-navy"><div class="mb-1"><span class="text-gray-400 uppercase tracking-wider text-[10px] mr-2">Date</span> <b>{fmt_date}</b></div><div><span class="text-gray-400 uppercase tracking-wider text-[10px] mr-2">No.</span> <b>{inv_num}</b></div></div></div></div></header>
                                    <main class="flex-grow relative z-10">
                                        <div class="flex mb-10 bg-gray-50 border-l-4 border-vesak-navy"><div class="w-1/2 p-4 border-r border-gray-200"><div class="text-[10px] font-bold text-vesak-gold uppercase mb-1">Billed To</div><div class="text-lg font-bold text-vesak-navy">{c_name}</div><div class="flex gap-4 mt-2 text-xs text-gray-600"><div class="flex items-center gap-1"><i class="fas fa-user text-vesak-gold"></i> {c_gender}</div><div class="flex items-center gap-1"><i class="fas fa-birthday-cake text-vesak-gold"></i> {c_age} Yrs</div></div></div><div class="w-1/2 p-4 flex flex-col justify-center"><div class="flex items-center gap-2 text-xs text-gray-600 mb-2"><i class="fas fa-phone-alt text-vesak-gold w-4"></i> {c_mob}</div><div class="flex items-start gap-2 text-xs text-gray-600"><i class="fas fa-map-marker-alt text-vesak-gold w-4 mt-0.5"></i> <span class="leading-tight">{c_addr}</span></div></div></div>
                                        <table class="w-full mb-8"><thead><tr class="bg-vesak-navy text-white text-xs uppercase tracking-wider text-left"><th class="p-3 w-3/5">Description</th><th class="p-3 w-2/5 text-right">Amount</th></tr></thead><tbody><tr class="border-b border-gray-100"><td class="p-4 align-top"><div class="font-bold text-sm text-gray-800">{clean_plan}</div>{desc_col_html}</td><td class="p-4 text-right font-bold text-sm text-gray-800 align-top">{amount_col_html}</td></tr></tbody></table>
                                        <div class="grid grid-cols-2 gap-8"><div><h4 class="text-xs font-bold text-vesak-navy uppercase border-b border-vesak-gold pb-1 mb-3">Services Included</h4><ul class="list-disc pl-4 space-y-1">{inc_html}</ul></div><div><h4 class="text-xs font-bold text-gray-400 uppercase border-b border-gray-200 pb-1 mb-3">Services Not Included</h4><ul class="columns-1 text-[10px] text-gray-400 space-y-1">{exc_html}</ul></div></div>
                                        {notes_section}
                                        <div class="text-center text-xs text-gray-400 mt-12 mb-6 italic">Thank you for choosing Vesak Care Foundation!</div>
                                    </main>
                                    <footer class="relative z-10 mt-auto w-full"><div class="w-full h-px bg-gradient-to-r from-gray-100 via-vesak-gold to-gray-100 opacity-50 mb-4"></div><div class="flex justify-between items-end text-xs text-gray-500"><div><p class="font-serif italic text-vesak-navy mb-1 text-sm">Our Offices</p><div class="flex gap-2"><span>Pune</span><span class="text-vesak-gold">•</span><span>Mumbai</span><span class="text-vesak-gold">•</span><span>Kolhapur</span></div></div><div class="flex flex-col items-end gap-1"><span class="flex items-center gap-2"><img src="data:image/png;base64,{ig_b64}" class="w-3 h-3 mr-1"> @VesakCare</span><span class="flex items-center gap-2"><img src="data:image/png;base64,{fb_b64}" class="w-3 h-3 mr-1"> @VesakCare</span></div></div><div class="mt-4 w-full h-1 bg-vesak-navy"></div></footer>
                                </div>
                                <script>function generatePDF() {{ const element = document.getElementById('invoice-content'); const opt = {{ margin: 0, filename: 'Invoice_{c_name}.pdf', image: {{ type: 'jpeg', quality: 0.98 }}, html2canvas: {{ scale: 2, useCORS: true, scrollY: 0 }}, jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }} }}; html2pdf().set(opt).from(element).save(); }}</script>
                            </body>
                            </html>
                            """
                            components.html(html_template, height=1000, scrolling=True)

            # === TAB 2: FORCE NEW INVOICE ===
            with tab2:
                render_invoice_ui(mode="force_new")

            # === TAB 3: DUPLICATE INVOICE (REPRINT) ===
            with tab3:
                st.header("📄 Duplicate / Reprint Invoice")
                if not df_history.empty and 'Customer Name' in df_history.columns:
                    reprint_data = df_history[df_history['Invoice Number'].str.strip() != ""]
                    if not reprint_data.empty:
                        reprint_data['ReprintDisplay'] = (
                            reprint_data['Invoice Number'].astype(str) + " | " + 
                            reprint_data['Customer Name'].astype(str) + " | " + 
                            reprint_data['Date'].astype(str)
                        )
                        selected_reprint = st.selectbox("Select Invoice to Reprint:", [""] + reprint_data['ReprintDisplay'].tolist())
                        
                        if selected_reprint:
                            inv_to_reprint = selected_reprint.split(" | ")[0].strip()
                            row_data = reprint_data[reprint_data['Invoice Number'] == inv_to_reprint].iloc[0]
                            st.divider()
                            st.info(f"Generating Duplicate Copy for Invoice: {inv_to_reprint}")
                            
                            c_name_rep = str(row_data.get('Customer Name', ''))
                            inv_num_rep = str(row_data.get('Invoice Number', ''))
                            fmt_date_rep = str(row_data.get('Date', ''))
                            c_plan_rep = str(row_data.get('Plan', ''))
                            c_gender_rep = str(row_data.get('Gender', ''))
                            c_age_rep = str(row_data.get('Age', ''))
                            c_mob_rep = str(row_data.get('Mobile', ''))
                            c_addr_rep = str(row_data.get('Address', ''))
                            desc_html_rep = f"""<div style="margin-top: 4px;"><div style="font-size: 12px; color: #4a4a4a; font-weight: bold;">{str(row_data.get('Shift', ''))}</div><div style="font-size: 10px; color: #777; font-style: italic; margin-top: 2px;">{str(row_data.get('Period', ''))}</div></div>"""
                            try: amt_unit = float(row_data.get('Amount', 0))
                            except: amt_unit = 0.0
                            try: amt_paid = float(row_data.get('Amount Paid', 0))
                            except: amt_paid = 0.0
                            details_txt = str(row_data.get('Details', ''))

                            amount_html_rep = f"""<div style="text-align: right; font-size: 13px; color: #555;"><div style="margin-bottom: 4px;">{str(row_data.get('Shift', ''))} / {str(row_data.get('Period', ''))} = <b>₹ {amt_unit:.0f}</b></div><div style="color: #CC4E00; font-weight: bold; font-size: 14px; margin: 2px 0;">X</div><div style="font-weight: bold; font-size: 13px; margin: 2px 0; color: #333;">{details_txt}</div><div style="border-bottom: 1px solid #ccc; width: 100%; margin: 6px 0;"></div><div style="display: flex; justify-content: flex-end; align-items: center; gap: 8px;"><span style="font-size: 13px; font-weight: 800; color: #002147; text-transform: uppercase;">TOTAL - </span><span style="font-size: 16px; font-weight: bold; color: #000;">Rs. {amt_paid:.0f}</span></div></div>"""
                            inc_def_rep = SERVICES_MASTER.get(c_plan_rep, ["Standard Services"])
                            inc_html_rep = "".join([f'<li class="mb-1 text-xs text-gray-700">{item}</li>' for item in inc_def_rep if item != "All"])
                            notes_raw_rep = str(row_data.get('Notes / Remarks', ''))
                            notes_sec_rep = ""
                            if notes_raw_rep: notes_sec_rep = f"""<div class="mt-6 p-4 bg-gray-50 border border-gray-100 rounded"><h4 class="font-bold text-vesak-navy text-xs mb-1">NOTES</h4><p class="text-xs text-gray-600 whitespace-pre-wrap">{notes_raw_rep}</p></div>"""

                            html_rep = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script>tailwind.config = {{ theme: {{ extend: {{ colors: {{ vesak: {{ navy: '#002147', gold: '#C5A065', orange: '#CC4E00' }} }}, fontFamily: {{ serif: ['"Playfair Display"', 'serif'], sans: ['"Lato"', 'sans-serif'] }} }} }} }}</script><style>@import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&family=Playfair+Display:wght@400;600;700&display=swap'); body {{ font-family: 'Lato', sans-serif; background: #f0f0f0; }} .invoice-page {{ background: white; width: 210mm; min-height: 297mm; margin: 20px auto; padding: 40px; position: relative; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); display: flex; flex-direction: column; }} .watermark-container {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; opacity: 0.03; pointer-events: none; z-index: 0; }} .watermark-text {{ font-family: 'Playfair Display', serif; font-size: 80px; font-weight: 700; color: #002147; letter-spacing: 0.3em; }} @media print {{ body {{ background: white; -webkit-print-color-adjust: exact; }} .invoice-page {{ margin: 0; box-shadow: none; width: 100%; height: 100%; padding: 40px; }} .no-print {{ display: none !important; }} .watermark-container {{ opacity: 0.015 !important; }} }}</style></head><body class="py-10"><div class="max-w-[210mm] mx-auto mb-6 flex justify-end no-print px-4"><button onclick="generatePDF()" class="bg-vesak-navy text-white px-6 py-2 rounded shadow hover:bg-vesak-gold transition font-bold text-xs uppercase tracking-widest"><i class="fas fa-download mr-2"></i> Download PDF</button></div><div class="invoice-page" id="invoice-content"><div class="watermark-container"><img src="data:image/png;base64,{logo_b64}" style="width: 300px; opacity: 0.3;"><div class="watermark-text mt-4">VESAK</div></div><header class="relative z-10 w-full mb-10"><div class="flex justify-between items-start border-b border-gray-100 pb-6"><div class="flex items-center gap-5"><img src="data:image/png;base64,{logo_b64}" class="w-20 h-auto"><div><h1 class="font-serif text-2xl font-bold text-vesak-navy tracking-wide leading-none mb-2">Vesak Care <span class="text-vesak-gold font-normal">Foundation</span></h1><div class="flex flex-col text-xs text-gray-500 font-light tracking-wide space-y-0.5"><span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Web</span> vesakcare.com</span><span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Email</span> vesakcare@gmail.com</span><span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Phone</span> +91 7777 000 878</span></div></div></div><div class="text-right"><span class="block font-serif text-3xl text-gray-200 tracking-widest mb-2">INVOICE</span><div class="text-xs text-vesak-navy"><div class="mb-1"><span class="text-gray-400 uppercase tracking-wider text-[10px] mr-2">Date</span> <b>{fmt_date_rep}</b></div><div><span class="text-gray-400 uppercase tracking-wider text-[10px] mr-2">No.</span> <b>{inv_num_rep}</b></div></div></div></div></header><main class="flex-grow relative z-10"><div class="flex mb-10 bg-gray-50 border-l-4 border-vesak-navy"><div class="w-1/2 p-4 border-r border-gray-200"><div class="text-[10px] font-bold text-vesak-gold uppercase mb-1">Billed To</div><div class="text-lg font-bold text-vesak-navy">{c_name_rep}</div><div class="flex gap-4 mt-2 text-xs text-gray-600"><div class="flex items-center gap-1"><i class="fas fa-user text-vesak-gold"></i> {c_gender_rep}</div><div class="flex items-center gap-1"><i class="fas fa-birthday-cake text-vesak-gold"></i> {c_age_rep} Yrs</div></div></div><div class="w-1/2 p-4 flex flex-col justify-center"><div class="flex items-center gap-2 text-xs text-gray-600 mb-2"><i class="fas fa-phone-alt text-vesak-gold w-4"></i> {c_mob_rep}</div><div class="flex items-start gap-2 text-xs text-gray-600"><i class="fas fa-map-marker-alt text-vesak-gold w-4 mt-0.5"></i> <span class="leading-tight">{c_addr_rep}</span></div></div></div><table class="w-full mb-8"><thead><tr class="bg-vesak-navy text-white text-xs uppercase tracking-wider text-left"><th class="p-3 w-3/5">Description</th><th class="p-3 w-2/5 text-right">Amount</th></tr></thead><tbody><tr class="border-b border-gray-100"><td class="p-4 align-top"><div class="font-bold text-sm text-gray-800">{c_plan_rep}</div>{desc_html_rep}</td><td class="p-4 text-right font-bold text-sm text-gray-800 align-top">{amount_html_rep}</td></tr></tbody></table><div class="grid grid-cols-2 gap-8"><div><h4 class="text-xs font-bold text-vesak-navy uppercase border-b border-vesak-gold pb-1 mb-3">Services Included</h4><ul class="list-disc pl-4 space-y-1">{inc_html_rep}</ul></div></div>{notes_sec_rep}<div class="text-center text-xs text-gray-400 mt-12 mb-6 italic">Thank you for choosing Vesak Care Foundation!</div></main><footer class="relative z-10 mt-auto w-full"><div class="w-full h-px bg-gradient-to-r from-gray-100 via-vesak-gold to-gray-100 opacity-50 mb-4"></div><div class="flex justify-between items-end text-xs text-gray-500"><div><p class="font-serif italic text-vesak-navy mb-1 text-sm">Our Offices</p><div class="flex gap-2"><span>Pune</span><span class="text-vesak-gold">•</span><span>Mumbai</span><span class="text-vesak-gold">•</span><span>Kolhapur</span></div></div><div class="flex flex-col items-end gap-1"><span class="flex items-center gap-2"><img src="data:image/png;base64,{ig_b64}" class="w-3 h-3 mr-1"> @VesakCare</span><span class="flex items-center gap-2"><img src="data:image/png;base64,{fb_b64}" class="w-3 h-3 mr-1"> @VesakCare</span></div></div><div class="mt-4 w-full h-1 bg-vesak-navy"></div></footer></div><script>function generatePDF() {{ const element = document.getElementById('invoice-content'); const opt = {{ margin: 0, filename: 'Invoice_Copy.pdf', image: {{ type: 'jpeg', quality: 0.98 }}, html2canvas: {{ scale: 2, useCORS: true, scrollY: 0 }}, jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }} }}; html2pdf().set(opt).from(element).save(); }}</script></body></html>"""
                            components.html(html_rep, height=1000, scrolling=True)

            # === TAB 4: MANAGE SERVICES (UPDATED WITH DATE FILTER) ===
            with tab4:
                st.header("🛑 Manage Active Services")
                df_hist = get_history_data(sheet_obj)
                if not df_hist.empty:
                    df_hist = df_hist.fillna("")
                    if 'Service Ended' not in df_hist.columns:
                        st.warning("⚠️ 'Service Ended' column not found in History sheet.")
                    else:
                        active_services = df_hist[df_hist['Service Ended'].astype(str).str.strip() == ""]
                        col_m1, col_m2 = st.columns([1, 2])
                        with col_m1: use_filter = st.checkbox("Filter by Invoice Date", key="man_use_filter")
                        if use_filter:
                            with col_m2:
                                filter_date_manage = st.date_input("Show services started on Selected Date & +1 Day:", value=datetime.date.today(), key="man_filter_date")
                                d_start_manage = filter_date_manage
                                d_end_manage = filter_date_manage + datetime.timedelta(days=1)
                            if not active_services.empty and 'Date' in active_services.columns:
                                active_services['DateObj'] = pd.to_datetime(active_services['Date'], errors='coerce').dt.date
                                active_services = active_services[(active_services['DateObj'] >= d_start_manage) & (active_services['DateObj'] <= d_end_manage)]
                        if not active_services.empty:
                            active_services['Display'] = (active_services['Invoice Number'].astype(str) + " - " + active_services['Customer Name'].astype(str) + " (" + active_services['Date'].astype(str) + ")")
                            options = [""] + active_services['Display'].tolist()
                            selected_service_disp = st.selectbox("Select Active Service to END:", options)
                            manual_end_date = st.date_input("Service End Date:", value=datetime.date.today())
                            if selected_service_disp:
                                inv_to_end = selected_service_disp.split(" - ")[0].strip()
                                name_to_end = selected_service_disp.split(" - ")[1].split(" (")[0]
                                st.warning(f"Are you sure you want to end service for **{name_to_end}** (Invoice: {inv_to_end}) on **{manual_end_date}**?")
                                if st.button("Mark Service as ENDED 🛑"):
                                    success, time_ended = mark_service_ended(sheet_obj, inv_to_end, manual_end_date)
                                    if success:
                                        st.success(f"✅ Service for {name_to_end} marked as ENDED at {time_ended}")
                                        st.rerun()
                                    else: st.error(f"❌ Failed to update: {time_ended}")
                        else:
                            if use_filter: st.info(f"No active services found starting between {d_start_manage} and {d_end_manage}.")
                            else: st.info("No active services found (All rows have End Dates).")
                else: st.info("History sheet is empty.")

        except Exception as e:
                st.error(f"Error: {e}")

import streamlit as st
import pandas as pd
import base64
import os
import datetime
import requests
from io import BytesIO
from PIL import Image, ImageFile
import streamlit.components.v1 as components

# --- CRITICAL FIX FOR BROKEN IMAGES ---
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ==========================================
# 1. SETUP & ASSET GENERATION
# ==========================================
st.set_page_config(page_title="Vesak Care Invoice", layout="wide", page_icon="🏥")

CONFIG_FILE = "path_config.txt"
URL_CONFIG_FILE = "url_config.txt"
LOGO_FILE = "logo.png"

# --- AUTO-DOWNLOAD ICONS (Reliable Method) ---
def download_and_save_icon(url, filename):
    """Downloads an icon from the web and saves it as a clean, small PNG."""
    if not os.path.exists(filename):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                # Resize to small icon size to keep PDF light
                img = img.resize((32, 32)) 
                img.save(filename, format="PNG")
                return True
        except:
            return False
    return True

# Public URLs for standard icons
IG_URL = "https://cdn-icons-png.flaticon.com/512/2111/2111463.png" # Instagram Color
FB_URL = "https://cdn-icons-png.flaticon.com/512/5968/5968764.png" # Facebook Color

# Trigger download on startup
download_and_save_icon(IG_URL, "icon-ig.png")
download_and_save_icon(FB_URL, "icon-fb.png")

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def load_config_path(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r") as f: return f.read().strip()
    return ""

def save_config_path(path, file_name):
    with open(file_name, "w") as f: f.write(path.replace('"', '').strip())
    return path

def get_clean_image_base64(file_path):
    if not os.path.exists(file_path): return None
    try:
        img = Image.open(file_path).convert("RGBA")
        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except: return None

def robust_file_downloader(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    download_url = url.split('?')[0] + "?download=1" if "1drv.ms" in url else url
    response = requests.get(download_url, headers=headers, verify=False)
    if response.status_code == 200: return BytesIO(response.content)
    raise Exception("Download failed")

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

# ==========================================
# 3. DATA LOGIC
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
    "Plan A: Patient Attendant Care": "Patient Care",
    "Plan B: Skilled Nursing": "Nursing Care",
    "Plan C: Chronic Management": "Chronic Management Care",
    "Plan D: Elderly Companion": "Elderly Companion Care",
    "Plan E: Maternal & Newborn": "Maternal & Newborn Care",
    "Plan F: Rehabilitative Care": "Rehabilitative Care",
    "A-la-carte Services": "Other Services"
}

COLUMN_ALIASES = {
    'Name': ['Name', 'name', 'patient name', 'client name'],
    'Mobile': ['Mobile', 'mobile', 'phone', 'contact'],
    'Address': ['Address', 'address', 'location', 'city'],
    'Gender': ['Gender', 'gender', 'sex'],
    'Age': ['Age', 'age'],
    'Service Required': ['Service Required', 'service required', 'plan'],
    'Sub Service': ['Sub Service', 'sub service', 'sub plan'],
    'Final Rate': ['Final Rate', 'final rate', 'amount', 'total amount'],
    'Unit Rate': ['Rate Agreed (₹)', 'rate agreed', 'unit rate', 'per day rate', 'rate agreed'],
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

# --- COLUMN A: DESCRIPTION LOGIC ---
def construct_description_html(row):
    shift_raw = str(row.get('Shift', '')).strip()
    recurring = str(row.get('Recurring', '')).strip().lower()
    period_raw = str(row.get('Period', '')).strip()
    visits_raw = row.get('Visits', 0)

    shift_map = {"12-hr Day": "12 Hours - Day", "12-hr Night": "12 Hours - Night", "24-hr": "24 Hours"}
    shift_str = shift_map.get(shift_raw, shift_raw)
    time_suffix = " (Time)" if "12" in shift_str else ""
    
    try: visits = int(float(visits_raw)) if visits_raw and str(visits_raw).lower() != 'nan' else 0
    except: visits = 0

    p_lower = period_raw.lower()
    if 'dai' in p_lower: p_single, p_multi = "Day", "Days"
    elif 'week' in p_lower: p_single, p_multi = "Week", "Weeks"
    elif 'month' in p_lower: p_single, p_multi = "Month", "Months"
    else: p_single, p_multi = period_raw, period_raw

    if recurring == 'yes':
        line1 = f"{shift_str}{time_suffix} - {period_raw}"
        line2 = "Till the Service Required"
    else:
        p_final = p_single if visits == 1 else p_multi
        line1 = f"{shift_str}{time_suffix}"
        line2 = f"For {visits} {p_final}"

    return f"""
    <div style="margin-top: 4px;">
        <div style="font-size: 12px; color: #4a4a4a; font-weight: bold;">{line1}</div>
        <div style="font-size: 10px; color: #777; font-style: italic; margin-top: 2px;">{line2}</div>
    </div>
    """

# --- COLUMN B: AMOUNT & MATH ---
def construct_amount_html(row):
    shift_raw = str(row.get('Shift', '')).strip()
    recurring = str(row.get('Recurring', '')).strip().lower()
    period_raw = str(row.get('Period', '')).strip()
    visits_raw = row.get('Visits', 0)
    
    final_rate = row.get('Final Rate', 0)
    if isinstance(final_rate, pd.Series): final_rate = final_rate.iloc[0]
    unit_rate = row.get('Unit Rate', 0)
    if isinstance(unit_rate, pd.Series): unit_rate = unit_rate.iloc[0]

    shift_map = {"12-hr Day": "12 Hours - Day", "12-hr Night": "12 Hours - Night", "24-hr": "24 Hours"}
    shift_str = shift_map.get(shift_raw, shift_raw)
    time_suffix = " (Time)" if "12" in shift_str else ""
    shift_display = f"{shift_str}{time_suffix}"

    try: visits = int(float(visits_raw)) if visits_raw and str(visits_raw).lower() != 'nan' else 0
    except: visits = 0

    if unit_rate == 0 and visits > 0 and final_rate > 0:
        unit_rate = int(final_rate / visits)
    if visits == 0 and final_rate > 0:
        visits = 1
        if unit_rate == 0: unit_rate = final_rate

    p_lower = period_raw.lower()
    if 'dai' in p_lower: p_single, p_multi = "Day", "Days"
    elif 'week' in p_lower: p_single, p_multi = "Week", "Weeks"
    elif 'month' in p_lower: p_single, p_multi = "Month", "Months"
    else: p_single, p_multi = period_raw, period_raw
    
    p_final = p_single if visits == 1 else p_multi

    if recurring == 'yes' and 'month' in p_lower:
        duration_text = "Per Month"
    else:
        duration_text = f"{visits} {p_final}"

    return f"""
    <div style="text-align: right; font-size: 12px; color: #666;">
        <div style="display: flex; justify-content: flex-end; align-items: center;">
            <span>{shift_display} / {p_single} = <b style="color: #333;">₹ {unit_rate:,}</b></span>
        </div>
        <div style="color: #CC4E00; font-weight: bold; font-size: 14px; margin: 2px 0;">X</div>
        <div>{duration_text}</div>
        <div style="border-bottom: 1px solid #ccc; width: 100%; margin: 4px 0;"></div>
        <div style="display: flex; justify-content: flex-end; gap: 5px;">
            <span style="font-size: 10px; font-weight: bold; color: #002147; text-transform: uppercase;">Total -</span>
            <span style="font-size: 14px; font-weight: bold; color: #000;">₹ {final_rate:,}</span>
        </div>
    </div>
    """

def make_html_list(items):
    if not items: return ""
    return "".join([f'<div style="margin-bottom:3px; font-size:10px;">• {x}</div>' for x in items])

def chunk_list(data, num_chunks):
    chunks = [[] for _ in range(num_chunks)]
    for i, item in enumerate(data): chunks[i % num_chunks].append(item)
    return chunks

# ==========================================
# 4. UI & LOGIC
# ==========================================
st.title("🏥 Vesak Care - Invoice Generator")

logo_b64 = get_clean_image_base64(LOGO_FILE)
ig_b64 = get_clean_image_base64("icon-ig.png")
fb_b64 = get_clean_image_base64("icon-fb.png")

if not logo_b64: st.sidebar.warning("⚠️ Logo not found.")

with st.sidebar:
    st.header("📂 Data Source")
    data_source = st.radio("Load Method:", ["Upload File", "OneDrive URL", "Local Path"])

raw_file_obj = None
if data_source == "Upload File":
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
    if uploaded_file: raw_file_obj = uploaded_file
elif data_source == "OneDrive URL":
    current_url = load_config_path(URL_CONFIG_FILE)
    url_input = st.text_input("Link:", value=current_url)
    if st.button("Load"): save_config_path(url_input, URL_CONFIG_FILE); st.rerun()
    if current_url:
        try: raw_file_obj = robust_file_downloader(current_url); st.success("Connected")
        except: st.error("Link Error")
elif data_source == "Local Path":
    current_path = load_config_path(CONFIG_FILE)
    path_input = st.text_input("Path:", value=current_path)
    if st.button("Save"): save_config_path(path_input, CONFIG_FILE); st.rerun()
    if current_path and os.path.exists(current_path): raw_file_obj = current_path

if raw_file_obj:
    try:
        try:
            xl = pd.ExcelFile(raw_file_obj)
            sheet_names = xl.sheet_names
            if hasattr(raw_file_obj, 'seek'): raw_file_obj.seek(0)
            default_ix = 0
            if 'Confirmed' in sheet_names: default_ix = sheet_names.index('Confirmed')
            with st.sidebar:
                selected_sheet = st.selectbox("Sheet:", sheet_names, index=default_ix)
            df = pd.read_excel(raw_file_obj, sheet_name=selected_sheet)
        except:
            if hasattr(raw_file_obj, 'seek'): raw_file_obj.seek(0)
            df = pd.read_csv(raw_file_obj)

        df = normalize_columns(df, COLUMN_ALIASES)
        missing = [k for k in ['Name', 'Mobile', 'Final Rate', 'Service Required', 'Unit Rate'] if k not in df.columns]
        if missing: st.error(f"Missing columns: {missing}"); st.stop()
        
        st.success("✅ Data Loaded")
        
        df['Label'] = df['Name'].astype(str) + " (" + df['Mobile'].astype(str) + ")"
        selected_label = st.selectbox("Select Customer:", df['Label'].unique())
        row = df[df['Label'] == selected_label].iloc[0]
        
        # Prepare Data
        c_plan = row.get('Service Required', '')
        c_sub = row.get('Sub Service', '')
        c_ref_date = format_date_with_suffix(row.get('Call Date', 'N/A'))
        c_notes_raw = str(row.get('Notes', '')) if not pd.isna(row.get('Notes', '')) else ""
        c_name = row.get('Name', '')
        c_gender = row.get('Gender', '')
        c_age = str(int(row.get('Age', 0))) if pd.notna(row.get('Age')) and row.get('Age') != '' else ""
        c_addr = row.get('Address', '')
        c_mob = row.get('Mobile', '')
        
        inc_def, exc_def = get_base_lists(c_plan, c_sub)
        desc_col_html = construct_description_html(row) 
        amount_col_html = construct_amount_html(row)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Plan:** {PLAN_DISPLAY_NAMES.get(c_plan, c_plan)}")
            inv_date = st.date_input("Date:", value=datetime.date.today())
            st.caption(f"Ref Date: {c_ref_date}")
        with col2:
            final_exc = st.multiselect("Excluded (Editable):", options=exc_def + ["Others"], default=exc_def)
            
        st.write("**Included Services:**")
        st.text(", ".join(inc_def))
        
        final_notes = st.text_area("Notes:", value=c_notes_raw)
        
        if st.button("Generate Invoice"):
            
            clean_plan = PLAN_DISPLAY_NAMES.get(c_plan, c_plan)
            fmt_date = format_date_with_suffix(inv_date)
            inv_num = inv_date.strftime('%Y%m%d') + "-001"
            
            inc_html = "".join([f'<li class="mb-1 text-xs text-gray-700">{item}</li>' for item in inc_def])
            exc_html = "".join([f'<li class="mb-1 text-[10px] text-gray-500">{item}</li>' for item in final_exc])
            
            notes_section = ""
            if final_notes:
                notes_section = f"""<div class="mt-6 p-4 bg-gray-50 border border-gray-100 rounded"><h4 class="font-bold text-vesak-navy text-xs mb-1">NOTES</h4><p class="text-xs text-gray-600 whitespace-pre-wrap">{final_notes}</p></div>"""

            # --- HTML TEMPLATE (YOUR DESIGN + DATA) ---
            html_template = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Invoice</title>
                <script src="https://cdn.tailwindcss.com"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
                <script>
                    tailwind.config = {{
                        theme: {{
                            extend: {{
                                colors: {{ vesak: {{ navy: '#002147', gold: '#C5A065', orange: '#CC4E00' }} }},
                                fontFamily: {{ serif: ['"Playfair Display"', 'serif'], sans: ['"Lato"', 'sans-serif'] }}
                            }}
                        }}
                    }}
                </script>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&family=Playfair+Display:wght@400;600;700&display=swap');
                    body {{ font-family: 'Lato', sans-serif; background: #f0f0f0; }}
                    .invoice-page {{
                        background: white; width: 210mm; min-height: 296mm;
                        margin: 20px auto; padding: 40px; position: relative;
                        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); display: flex; flex-direction: column;
                    }}
                    .watermark-container {{
                        position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        display: flex; flex-direction: column; align-items: center;
                        opacity: 0.03; pointer-events: none; z-index: 0;
                    }}
                    .watermark-text {{
                        font-family: 'Playfair Display', serif; font-size: 80px;
                        font-weight: 700; color: #002147; letter-spacing: 0.3em;
                    }}
                    @media print {{
     				@page {{ margin: 0; size: auto; }} /* Kills browser default margins */
    				body {{ margin: 0; padding: 0; -webkit-print-color-adjust: exact; }}
    				.invoice-page {{
    				margin: 0;
        			width: 210mm;
        			height: 296mm; /* 1mm buffer to prevent page 2 */
        			padding: 40px;
				box-shadow: none;
        			overflow: hidden; /* Cuts off any ghost pixels */
        			page-break-after: avoid; /* Forbids new page */
				page-break-inside: avoid;
    			}}
                        .no-print {{ display: none !important; }}
                        .watermark-container {{ opacity: 0.012 !important; }}
                    }}
                </style>
            </head>
            <body class="py-10">
                <div class="max-w-[210mm] mx-auto mb-6 flex justify-end no-print px-4">
                    <button onclick="generatePDF()" class="bg-vesak-navy text-white px-6 py-2 rounded shadow hover:bg-vesak-gold transition font-bold text-xs uppercase tracking-widest">
                        <i class="fas fa-download mr-2"></i> Download PDF
                    </button>
                </div>

                <div class="invoice-page" id="invoice-content">
                    <div class="watermark-container">
                        <img src="data:image/png;base64,{logo_b64}" style="width: 300px; opacity: 0.3;">
                        <div class="watermark-text mt-4">VESAK</div>
                    </div>

                    <header class="relative z-10 w-full mb-10">
                        <div class="flex justify-between items-start border-b border-gray-100 pb-6">
                            <div class="flex items-center gap-5">
                                <img src="data:image/png;base64,{logo_b64}" class="w-20 h-auto">
                                <div>
                                    <h1 class="font-serif text-2xl font-bold text-vesak-navy tracking-wide leading-none mb-2">
                                        Vesak Care <span class="text-vesak-gold font-normal">Foundation</span>
                                    </h1>
                                    <div class="flex flex-col text-xs text-gray-500 font-light tracking-wide space-y-0.5">
                                        <span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Web</span> vesakcare.com</span>
                                        <span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Email</span> vesakcare@gmail.com</span>
                                        <span><span class="font-bold text-vesak-gold uppercase w-12 inline-block">Phone</span> +91 7777 000 878</span>
                                    </div>
                                </div>
                            </div>
                            <div class="text-right">
                                <span class="block font-serif text-3xl text-gray-200 tracking-widest mb-2">INVOICE</span>
                                <div class="text-xs text-vesak-navy">
                                    <div class="mb-1"><span class="text-gray-400 uppercase tracking-wider text-[10px] mr-2">Date</span> <b>{fmt_date}</b></div>
                                    <div><span class="text-gray-400 uppercase tracking-wider text-[10px] mr-2">No.</span> <b>{inv_num}</b></div>
                                </div>
                            </div>
                        </div>
                    </header>

                    <main class="flex-grow relative z-10">
                        <div class="flex mb-10 bg-gray-50 border-l-4 border-vesak-navy">
                            <div class="w-1/2 p-4 border-r border-gray-200">
                                <div class="text-[10px] font-bold text-vesak-gold uppercase mb-1">Billed To</div>
                                <div class="text-lg font-bold text-vesak-navy">{c_name}</div>
                                <div class="flex gap-4 mt-2 text-xs text-gray-600">
                                    <div class="flex items-center gap-1"><i class="fas fa-user text-vesak-gold"></i> {c_gender}</div>
                                    <div class="flex items-center gap-1"><i class="fas fa-birthday-cake text-vesak-gold"></i> {c_age} Yrs</div>
                                </div>
                            </div>
                            <div class="w-1/2 p-4 flex flex-col justify-center">
                                <div class="flex items-center gap-2 text-xs text-gray-600 mb-2">
                                    <i class="fas fa-phone-alt text-vesak-gold w-4"></i> {c_mob}
                                </div>
                                <div class="flex items-start gap-2 text-xs text-gray-600">
                                    <i class="fas fa-map-marker-alt text-vesak-gold w-4 mt-0.5"></i> 
                                    <span class="leading-tight">{c_addr}</span>
                                </div>
                            </div>
                        </div>

                        <table class="w-full mb-8">
                            <thead>
                                <tr class="bg-vesak-navy text-white text-xs uppercase tracking-wider text-left">
                                    <th class="p-3 w-3/5">Description</th>
                                    <th class="p-3 w-2/5 text-right">Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr class="border-b border-gray-100">
                                    <td class="p-4 align-top">
                                        <div class="font-bold text-sm text-gray-800">{clean_plan}</div>
                                        {desc_col_html}
                                    </td>
                                    <td class="p-4 text-right font-bold text-sm text-gray-800 align-top">
                                        {amount_col_html}
                                    </td>
                                </tr>
                            </tbody>
                        </table>

                        <div class="grid grid-cols-2 gap-8">
                            <div>
                                <h4 class="text-xs font-bold text-vesak-navy uppercase border-b border-vesak-gold pb-1 mb-3">Services Included</h4>
                                <ul class="list-disc pl-4 space-y-1">{inc_html}</ul>
                            </div>
                            <div>
                                <h4 class="text-xs font-bold text-gray-400 uppercase border-b border-gray-200 pb-1 mb-3">Services Not Included</h4>
                                <ul class="columns-1 text-[10px] text-gray-400 space-y-1">{exc_html}</ul>
                            </div>
                        </div>

                        {notes_section}

                        <div class="text-center text-xs text-gray-400 mt-12 mb-6 italic">
                            Thank you for choosing Vesak Care Foundation!
                        </div>
                    </main>

                    <footer class="relative z-10 mt-auto w-full">
                        <div class="w-full h-px bg-gradient-to-r from-gray-100 via-vesak-gold to-gray-100 opacity-50 mb-4"></div>
                        <div class="flex justify-between items-end text-xs text-gray-500">
                            <div>
                                <p class="font-serif italic text-vesak-navy mb-1 text-sm">Our Offices</p>
                                <div class="flex gap-2">
                                    <span>Pune</span><span class="text-vesak-gold">•</span>
                                    <span>Mumbai</span><span class="text-vesak-gold">•</span>
                                    <span>Kolhapur</span>
                                </div>
                            </div>
                            <div class="flex flex-col items-end gap-1">
                                <span class="flex items-center gap-2"><img src="data:image/png;base64,{ig_b64}" class="w-3 h-3 mr-1"> @VesakCare</span>
                                <span class="flex items-center gap-2"><img src="data:image/png;base64,{fb_b64}" class="w-3 h-3 mr-1"> @VesakCare</span>
                            </div>
                        </div>
                        <div class="mt-4 w-full h-1 bg-vesak-navy"></div>
                    </footer>
                </div>

                <script>
                    function generatePDF() {{
                        const element = document.getElementById('invoice-content');
                        const opt = {{
                            margin: 0,
                            filename: 'Invoice_{c_name}.pdf',
                            image: {{ type: 'jpeg', quality: 0.98 }},
                            html2canvas: {{ scale: 2, useCORS: true }},
                            jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }},
                        }};
                        html2pdf().set(opt).from(element).save();
                    }}
                </script>
            </body>
            </html>
            """
            
            components.html(html_template, height=1000, scrolling=True)

    except Exception as e:
        st.error(f"Error: {e}")

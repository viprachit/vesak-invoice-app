import streamlit as st
import pandas as pd
import re
import os
import datetime
import requests
import base64
import ssl
import traceback
from io import BytesIO
from xhtml2pdf import pisa
import streamlit.components.v1 as components

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
st.set_page_config(page_title="Vesak Care Invoice", layout="wide", page_icon="🏥")

CONFIG_FILE = "path_config.txt"
URL_CONFIG_FILE = "url_config.txt"
LOGO_FILE = "logo.png"

def load_config_path(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            return f.read().strip()
    return ""

def save_config_path(path, file_name):
    clean_path = path.replace('"', '').strip()
    with open(file_name, "w") as f:
        f.write(clean_path)
    return clean_path

# ==========================================
# 2. IMAGE HANDLING
# ==========================================
def get_image_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    return None

# ==========================================
# 3. BRAIN: SERVICE DATA & RULES
# ==========================================

SERVICES_MASTER = {
    "Plan A: Patient Attendant Care": [
        "All", "Basic Care", "Assistance with Activities for Daily Living",
        "Feeding & Oral Hygiene", "Mobility Support & Transfers",
        "Bed Bath and Emptying Bedpans and Changing Diapers",
        "Catheter & Ostomy Care (If Attendant Knows)"
    ],
    "Plan B: Skilled Nursing": [
        "All", "Intravenous (IV) Therapy & Injections",
        "Medication Management & Administration", "Advanced Wound Care & Dressing",
        "Catheter & Ostomy Care", "Post-Surgical Care"
    ],
    "Plan C: Chronic Management": [
        "All", "Care for Bed-Ridden Patients", "Dementia & Alzheimer's Care",
        "Disability Support & Assistance"
    ],
    "Plan D: Elderly Companion": [
        "All", "Companionship & Conversation", "Fall Prevention & Mobility Support",
        "Light Meal Preparation"
    ],
    "Plan E: Maternal & Newborn": [
        "All", "Postnatal & Maternal Care", "Newborn Care Assistance"
    ],
    "Plan F: Rehabilitative Care": [
        "Therapeutic Massage", "Exercise Therapy", "Geriatic (Old Age) Rehabilitation",
        "Neuro Rehabilitaion",
        "Pain - Back | Leg | Knee | Foot | Shoulder | Ankle | Elbow | Wrist | Neck",
        "Post Operative Rehabilitation"
    ],
    "A-la-carte Services": [
        "Hospital Visits", "Medical Equipment Rental",
        "Medicines (Alopathy, Ayurvedic, Homeopathy)", "Diagnostic Services at Home",
        "Nutrition & Dietetic Consultation", "Ambulance", "Doctor Visits",
        "X-Ray", "Blood Collection"
    ]
}

STANDARD_PLANS = [
    "Plan A: Patient Attendant Care",
    "Plan B: Skilled Nursing",
    "Plan C: Chronic Management",
    "Plan D: Elderly Companion",
    "Plan E: Maternal & Newborn"
]

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
    'Name': ['Name', 'name', 'patient name', 'client name', 'patient', 'client'],
    'Mobile': ['Mobile', 'mobile', 'phone', 'contact', 'mobile no', 'cell'],
    'Address': ['Address', 'address', 'location', 'city', 'residence'],
    'Service Required': ['Service Required', 'service required', 'plan', 'service', 'service name', 'inquiry'],
    'Sub Service': ['Sub Service', 'sub service', 'sub plan', 'services'],
    'Final Rate': ['Final Rate', 'final rate', 'final amount', 'amount'],
    'Call Date': ['Call Date', 'call date', 'date', 'inquiry date'],
    'Notes': ['Notes / Remarks', 'notes', 'remarks', 'comment', 'comments', 'description']
}

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================

def clean_text(text):
    if not isinstance(text, str): return str(text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\bAll\b,?', '', text, flags=re.IGNORECASE)
    text = text.replace(' ,', ',').strip(' ,')
    return text.strip()

def format_date_with_suffix(d):
    if pd.isna(d) or str(d).lower() == 'nan' or str(d).lower() == 'n/a':
        return "N/A"
    try:
        if not isinstance(d, (datetime.date, datetime.datetime)):
            d = pd.to_datetime(d)
        if isinstance(d, datetime.datetime):
            d = d.date()
        day = d.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return d.strftime(f"%b. {day}{suffix} %Y")
    except:
        return str(d)

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
            services = SERVICES_MASTER.get(plan_name, [])
            for item in services:
                if item.lower() == "all": continue
                cleaned = clean_text(item)
                if cleaned: not_included_clean.append(cleaned)
    else:
        for item in master_list:
            cleaned = clean_text(item)
            if cleaned and cleaned not in included_clean:
                not_included_clean.append(cleaned)
    return included_clean, list(set(not_included_clean))

def chunk_list(data, num_chunks):
    chunks = [[] for _ in range(num_chunks)]
    for i, item in enumerate(data):
        chunks[i % num_chunks].append(item)
    return chunks

def make_html_list(items):
    if not items: return ""
    return "".join([f'<div style="margin-bottom:3px; font-size:10px;">• {x}</div>' for x in items])

def convert_html_to_pdf(source_html):
    result = BytesIO()
    pisa_status = pisa.CreatePDF(source_html, dest=result)
    if pisa_status.err: return None
    return result.getvalue()

def normalize_columns(df, aliases):
    df.columns = df.columns.astype(str).str.strip()
    for standard_name, possible_aliases in aliases.items():
        if standard_name in df.columns:
            continue 
        match_found = False
        for alias in possible_aliases:
            for df_col in df.columns:
                if df_col.lower() == alias.lower():
                    df.rename(columns={df_col: standard_name}, inplace=True)
                    match_found = True
                    break 
            if match_found:
                break 
    return df

def robust_file_downloader(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    download_url = url
    if "1drv.ms" in url or "onedrive.live.com" in url:
        base_url = url.split('?')[0]
        download_url = base_url + "?download=1"
    response = requests.get(download_url, headers=headers, allow_redirects=True, verify=False)
    if response.status_code == 200:
        return BytesIO(response.content)
    else:
        raise Exception(f"Failed to download. Status Code: {response.status_code}")

# ==========================================
# 5. APP INTERFACE & FILE LOGIC
# ==========================================
st.title("🏥 Vesak Care - Invoice Generator")

# Check for Logo
logo_b64 = get_image_base64(LOGO_FILE)
if not logo_b64:
    st.sidebar.warning("⚠️ 'logo.png' not found in folder.")

with st.sidebar:
    st.header("📂 Data Source")
    data_source = st.radio("Load Method:", ["Upload File", "OneDrive Web URL", "Local Path (Offline Only)"])

raw_file_obj = None

if data_source == "Upload File":
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=['xlsx', 'csv'])
    if uploaded_file:
        raw_file_obj = uploaded_file

elif data_source == "OneDrive Web URL":
    current_url = load_config_path(URL_CONFIG_FILE)
    url_input = st.text_input("Paste OneDrive Link:", value=current_url)
    if st.button("Load URL"):
        if url_input:
            save_config_path(url_input, URL_CONFIG_FILE)
            st.rerun()
    if current_url:
        try:
            raw_file_obj = robust_file_downloader(current_url)
            st.success("✅ Connected to OneDrive")
        except Exception as e:
            st.error(f"Download Error: {e}")

elif data_source == "Local Path (Offline Only)":
    current_path = load_config_path(CONFIG_FILE)
    path_input = st.text_input("Full File Path:", value=current_path)
    if st.button("Save Path"):
        if path_input:
            save_config_path(path_input, CONFIG_FILE)
            st.rerun()
    if current_path and os.path.exists(current_path):
        raw_file_obj = current_path
    elif current_path:
        st.warning("Path not found.")

if raw_file_obj:
    try:
        sheet_name = 0
        is_excel = False
        try:
            xl = pd.ExcelFile(raw_file_obj)
            is_excel = True
            sheet_names = xl.sheet_names
            
            # Reset pointer
            if hasattr(raw_file_obj, 'seek'):
                raw_file_obj.seek(0)

            default_ix = 0
            if 'Confirmed' in sheet_names: default_ix = sheet_names.index('Confirmed')
            with st.sidebar:
                st.divider()
                st.write("🔧 **Excel Settings**")
                selected_sheet = st.selectbox("Select Sheet:", sheet_names, index=default_ix)
            sheet_name = selected_sheet
        except:
            pass 

        if is_excel:
            df = pd.read_excel(raw_file_obj, sheet_name=sheet_name)
        else:
            if isinstance(raw_file_obj, str):
                df = pd.read_csv(raw_file_obj)
            else:
                raw_file_obj.seek(0)
                df = pd.read_csv(raw_file_obj)

        df = normalize_columns(df, COLUMN_ALIASES)
        missing = [k for k in ['Name', 'Mobile', 'Final Rate', 'Service Required'] if k not in df.columns]
        if missing:
            st.error(f"❌ Missing Columns: {missing}")
            st.stop()

        st.success("✅ Data Loaded")
        
        df['Label'] = df['Name'].astype(str) + " (" + df['Mobile'].astype(str) + ")"
        selected_label = st.selectbox("Select Customer:", df['Label'].unique())

        row = df[df['Label'] == selected_label].iloc[0]
        c_plan = row.get('Service Required', '')
        c_sub = row.get('Sub Service', '')
        c_call_date = row.get('Call Date', 'N/A')
        formatted_ref_date = format_date_with_suffix(c_call_date)
        
        c_notes_raw = row.get('Notes', '')
        if pd.isna(c_notes_raw) or str(c_notes_raw).lower() == 'nan':
            c_notes_raw = ""
        else:
            c_notes_raw = str(c_notes_raw)

        inc_default, exc_default = get_base_lists(c_plan, c_sub)

        st.divider()
        st.subheader("📝 Customize Invoice")
        
        display_name = PLAN_DISPLAY_NAMES.get(c_plan, c_plan)
        st.info(f"**Plan:** {display_name}")
        
        col_d1, col_d2 = st.columns([1, 2])
        with col_d1:
            today = datetime.date.today()
            invoice_date = st.date_input("Select Invoice Date:", value=today)
        with col_d2:
            st.write("") 
            st.write("") 
            st.caption(f"ℹ️ **Excel Reference:** {formatted_ref_date}")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.write("**✅ Services Included (Reference):**")
            if not inc_default:
                st.write("*None*")
            else:
                for item in inc_default:
                    st.markdown(f"- {item}")

        with col2:
            st.write("**❌ Services Not Included (Editable):**")
            final_excluded = st.multiselect("Modify List:", options=exc_default + ["Others"], default=exc_default)

        st.write("---")
        invoice_notes = st.text_area("✍️ **Notes / Remarks (Editable):**", value=c_notes_raw, height=100)

        if st.button("Generate Invoice Preview"):
            c_name = row.get('Name', '')
            c_addr = row.get('Address', '')
            c_mob = row.get('Mobile', '')
            raw_rate = row.get('Final Rate', 0)
            c_rate = raw_rate.iloc[0] if isinstance(raw_rate, pd.Series) else raw_rate
            
            final_plan_name = PLAN_DISPLAY_NAMES.get(c_plan, c_plan)
            inc_cols = chunk_list(inc_default, 2)
            exc_cols = chunk_list(final_excluded, 3)
            formatted_date = format_date_with_suffix(invoice_date)
            invoice_num_date = invoice_date.strftime('%Y%m%d')

            logo_html = ""
            watermark_html = ""
            if logo_b64:
                logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain;">'
                watermark_html = f"""<div id="watermark"><img src="data:image/png;base64,{logo_b64}" style="width: 500px; opacity: 0.1;"></div>"""

            notes_html = ""
            if invoice_notes:
                notes_html = f"""<div style="background-color: #fcfcfc; border: 1px solid #eee; padding: 10px; margin-top: 20px; font-size: 11px; color: #555;"><b>NOTES:</b><br>{invoice_notes.replace(chr(10), '<br>')}</div>"""

            # HTML STRUCTURE (Fixed - Footer moved to HTML body)
            invoice_body = f"""
            <html>
            <head>
                <style>
                    @page {{
                        size: A4;
                        margin: 30px;
                        margin-bottom: 50px;
                    }}
                    body {{ font-family: Helvetica, Arial, sans-serif; color: #333; }}
                    #watermark {{ position: fixed; top: 30%; left: 15%; opacity: 0.1; z-index: -1000; transform: rotate(-30deg); width: 100%; text-align: center; }}
                    .header-table {{ width: 100%; border: 0; }}
                    .bill-to-box {{ background-color: #f8f9fa; border-left: 4px solid #2c3e50; padding: 15px; }}
                    .service-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    .service-table th {{ background-color: #2c3e50; color: white; padding: 10px; text-align: left; }}
                    .service-table td {{ border: 1px solid #ddd; padding: 12px; }}
                    .section-title {{ margin-top: 20px; border-bottom: 2px solid #ccc; font-weight: bold; font-size: 13px; text-transform: uppercase; color: #2c3e50; }}
                    .footer {{ text-align: center; font-size: 10px; color: #777; margin-top: 50px; border-top: 1px solid #eee; padding-top: 10px; }}
                </style>
            </head>
            <body>
                {watermark_html}
                <table class="header-table">
                    <tr>
                        <td width="60%" valign="top">
                            {logo_html}
                            <div style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-top: 5px;">VESAK CARE FOUNDATION</div>
                            <div style="color: #555; font-size: 11px;">Pune, Maharashtra<br>Reg No: 123456789</div>
                        </td>
                        <td width="40%" align="right" valign="top">
                            <div style="font-size: 32px; font-weight: bold; color: #95a5a6;">INVOICE</div>
                            <div style="font-size: 12px; margin-top: 5px;">
                                <b>Date:</b> {formatted_date}<br>
                                <b>Invoice #:</b> {invoice_num_date}-001
                            </div>
                        </td>
                    </tr>
                </table>
                <hr style="border: 0; border-top: 2px solid #eee; margin: 15px 0;">
                <div class="bill-to-box">
                    <table width="100%">
                        <tr>
                            <td width="50%" valign="top">
                                <div style="color: #95a5a6; font-size: 9px; font-weight: bold; text-transform: uppercase;">Billed To</div>
                                <div style="font-size: 15px; font-weight: bold; margin-top: 2px;">{c_name}</div>
                                <div style="font-size: 12px; margin-top: 5px;">📞 {c_mob}</div>
                            </td>
                            <td width="50%" valign="top" style="padding-left: 20px;">
                                <div style="color: #95a5a6; font-size: 9px; font-weight: bold; text-transform: uppercase;">Address</div>
                                <div style="font-size: 12px; margin-top: 2px; line-height: 1.4;">{c_addr}</div>
                            </td>
                        </tr>
                    </table>
                </div>
                <br>
                <table class="service-table">
                    <thead>
                        <tr>
                            <th width="75%">Description</th>
                            <th width="25%" align="right">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><b>{final_plan_name}</b></td>
                            <td align="right">₹{c_rate}</td>
                        </tr>
                    </tbody>
                </table>
                
                <div class="section-title" style="border-color: #3498db;">Services Includes</div>
                <table width="100%" style="font-size: 11px; margin-top: 5px;">
                    <tr>
                        <td width="50%" valign="top">{make_html_list(inc_cols[0])}</td>
                        <td width="50%" valign="top">{make_html_list(inc_cols[1])}</td>
                    </tr>
                </table>

                <div class="section-title" style="border-color: #95a5a6; color: #7f8c8d;">Services Not Included</div>
                <table width="100%" style="font-size: 10px; color: #666; margin-top: 5px;">
                    <tr>
                        <td width="33%" valign="top">{make_html_list(exc_cols[0])}</td>
                        <td width="33%" valign="top">{make_html_list(exc_cols[1])}</td>
                        <td width="33%" valign="top">{make_html_list(exc_cols[2])}</td>
                    </tr>
                </table>

                {notes_html}

                <div class="footer">
                    Vesak Care Foundation | Pune, Maharashtra | +91 12345 67890 | info@vesakcare.com
                </div>
            </body>
            </html>
            """

            st.markdown("### 👁️ Live Preview")
            components.html(invoice_body, height=800, scrolling=True)
            
            pdf_bytes = convert_html_to_pdf(invoice_body)
            if pdf_bytes:
                st.download_button(label="📄 Download PDF Invoice", data=pdf_bytes, file_name=f"Invoice_{c_name.replace(' ', '_')}.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.write("Detailed Error for Debugging:")
        st.code(traceback.format_exc())

# helpers_utils.py
"""
Common helper utilities for Vesak Invoice app:
- ID normalization, referral cleaning
- Billing helpers (get_base_lists, construct_description_html, construct_amount_html)
- Filename generation, column alias normalization
- Small UI helpers: infer_role, render_invoice_ui (lightweight)
"""

from typing import Tuple, List, Dict, Any
import pandas as pd
import re
import datetime
from io import BytesIO
from PIL import Image
import base64

# ---------------------------
# CONSTANTS
# ---------------------------
COLUMN_ALIASES = {
    'Serial No.': ['Serial No.', 'serial no', 'sr no', 'sr. no.', 'id'],
    'Ref. No.': ['Ref. No.', 'ref no', 'ref. no.', 'reference no', 'reference number'],
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
    'Call Date': ['Call Date', 'call date', 'date'],
    'Notes': ['Notes / Remarks', 'notes', 'remark'],
    'Shift': ['Shift', 'shift'],
    'Recurring Service': ['Recurring Service', 'recurring', 'recurring service'],
    'Period': ['Period', 'period'],
    'Visits': ['Visits', 'visits', 'visit', 'vists'],
    'Referral Code': ['Referral Code', 'referral code', 'ref code'],
    'Referral Name': ['Referral Name', 'referral name', 'ref name'],
    'Referral Credit': ['Referral Credit', 'referral credit', 'ref credit']
}

# ---------------------------
# ID & TEXT CLEANING
# ---------------------------
def normalize_id(val) -> str:
    """Normalize id to integer-like string (no decimals) or empty string."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except:
        pass
    s_val = str(val).strip()
    if s_val == "" or s_val.lower() == "nan":
        return ""
    try:
        return str(int(float(s_val)))
    except:
        return s_val

def clean_referral_field(val) -> str:
    """Normalize referral fields (remove 'nan', 'none', empty)."""
    try:
        import pandas as pd
        if pd.isna(val): 
            return ""
    except:
        pass
    s_val = str(val).strip()
    if s_val.lower() in ("nan", "none", ""):
        return ""
    return s_val

# ---------------------------
# CACHED EXCLUSION LIST (client must be supplied)
# ---------------------------
def get_cached_exclusion_list(gspread_client, master_id: str, month_str: str) -> Tuple[List[str], List[str]]:
    """
    Returns (present_refs, ended_refs).
    NOTE: Accepts gspread client to avoid circular imports.
    """
    if not gspread_client or not master_id:
        return [], []
    present_refs = []
    ended_refs = []
    try:
        wb = gspread_client.open_by_key(master_id)
        try:
            sheet_check = wb.worksheet(month_str)
            data_check = sheet_check.get_all_records()
            df_check = pd.DataFrame(data_check)
            if not df_check.empty:
                df_check['Ref_Norm'] = df_check.get('Ref. No.', "").apply(normalize_id)
                df_check['Ser_Norm'] = df_check.get('Serial No.', "").apply(normalize_id)
                for _, row in df_check.iterrows():
                    key = f"{row.get('Ref_Norm','')}-{row.get('Ser_Norm','')}"
                    present_refs.append(key)
                    svc_end = str(row.get('Service Ended', '')).strip()
                    if svc_end:
                        ended_refs.append(key)
        except Exception:
            pass
    except Exception:
        return [], []
    return present_refs, ended_refs

# ---------------------------
# FILENAME GENERATOR
# ---------------------------
def generate_filename(doc_type: str, invoice_no: str, customer_name: str) -> str:
    prefix = {
        "Invoice": "IN",
        "Nurse": "NU",
        "Patient": "PA",
        "DUPLICATE INVOICE": "DUP"
    }.get(doc_type, "DOC")
    clean_name = re.sub(r'[^a-zA-Z0-9]', '-', str(customer_name)).upper().strip('-')
    invoice_no_clean = str(invoice_no).strip()
    return f"{prefix}-{invoice_no_clean}-{clean_name}.pdf"

# ---------------------------
# SERVICE / BILLING LOGIC
# ---------------------------
def get_base_lists(selected_plan: str, selected_sub_service: str):
    """
    Returns (included_clean, not_included_clean)
    Re-implements the Plan mapping logic; trimmed for brevity but fully usable.
    """
    # For production, keep the full mapping from your original code.
    SERVICES_MASTER = {
        "Plan A: Patient Attendant Care": ["All", "Basic Care", "Assistance with Activities for Daily Living", "Feeding & Oral Hygiene", "Mobility Support & Transfers", "Bed Bath and Emptying Bedpans", "Catheter & Ostomy Care"],
        "Plan B: Skilled Nursing": ["All", "Intravenous (IV) Therapy & Injections", "Medication Management", "Advanced Wound Care", "Catheter & Ostomy Care", "Post-Surgical Care"],
        "Plan C: Chronic Management": ["All", "Care for Bed-Ridden Patients", "Dementia & Alzheimer's Care", "Disability Support"],
        "Plan D: Elderly Companion": ["All", "Companionship & Conversation", "Fall Prevention & Mobility", "Light Meal Preparation"],
        "Plan E: Maternal & Newborn": ["All", "Postnatal & Maternal Care", "Newborn Care Assistance"],
        "Plan F: Rehabilitative Care": ["Therapeutic Massage", "Exercise Therapy", "Geriatric Rehabilitation", "Neuro Rehabilitation", "Pain Management", "Post Op Rehab"],
        "A-la-carte Services": ["Hospital Visits", "Medical Equipment", "Medicines", "Diagnostic Services", "Nutrition Consultation", "Ambulance", "Doctor Visits", "X-Ray", "Blood Collection"]
    }
    STANDARD_PLANS = list(SERVICES_MASTER.keys())[:5]

    base_plan = selected_plan
    if selected_plan not in SERVICES_MASTER:
        for k in SERVICES_MASTER.keys():
            if k in selected_plan:
                base_plan = k
                break
    master_list = SERVICES_MASTER.get(base_plan, [])
    if "All" in str(selected_sub_service) and base_plan in STANDARD_PLANS:
        included_raw = [s for s in master_list if s.lower() != "all"]
    else:
        included_raw = [x.strip() for x in str(selected_sub_service).split(',')]
    included_clean = sorted(list(set([s.strip() for s in included_raw if s and s.strip()])))
    not_included_clean = []
    if base_plan in STANDARD_PLANS:
        for plan_name in STANDARD_PLANS:
            if plan_name == base_plan:
                continue
            for item in SERVICES_MASTER.get(plan_name, []):
                if item.lower() == "all":
                    continue
                cleaned = item.strip()
                if cleaned:
                    not_included_clean.append(cleaned)
    else:
        for item in master_list:
            cleaned = item.strip()
            if cleaned and cleaned not in included_clean:
                not_included_clean.append(cleaned)
    return included_clean, list(set(not_included_clean))

def construct_description_html(row: dict) -> str:
    shift_raw = str(row.get('Shift', '')).strip()
    period_raw = str(row.get('Period', '')).strip()
    shift_map = {"12-hr Day": "12 Hours - Day", "12-hr Night": "12 Hours - Night", "24-hr": "24 Hours"}
    shift_str = shift_map.get(shift_raw, shift_raw)
    time_suffix = " (Time)" if "12" in shift_str else ""
    return f"""<div style="margin-top: 4px;"><div style="font-size: 12px; color: #4a4a4a; font-weight: bold;">{shift_str}{time_suffix}</div><div style="font-size: 10px; color: #777; font-style: italic; margin-top: 2px;">{period_raw}</div></div>"""

def construct_amount_html(row: dict, billing_qty: int) -> str:
    """
    Builds the right-hand billing HTML block that shows rate and paid-for details.
    Mirrors the detailed logic you had in app.py.
    """
    try:
        unit_rate = float(row.get('Unit Rate', row.get('Amount', 0) or 0))
    except Exception:
        unit_rate = 0.0
    try:
        visits_needed = int(float(row.get('Visits', 0)))
    except Exception:
        visits_needed = 0

    p_raw_check = str(row.get('Period', '')).strip()
    p_check_lower = p_raw_check.lower()
    shift_raw_check = str(row.get('Shift', '')).strip()
    shift_check_lower = shift_raw_check.lower()

    # Details text
    if "per visit" in shift_check_lower:
        details_text = f"Paid for {billing_qty} Visit" if billing_qty == 1 else f"Paid for {billing_qty} Visits"
    elif "daily" in p_check_lower:
        if billing_qty == 1:
            details_text = f"Paid for {billing_qty} Day"
        elif billing_qty % 7 == 0:
            weeks_val = int(billing_qty / 7)
            details_text = f"Paid for {weeks_val} Week" if weeks_val == 1 else f"Paid for {weeks_val} Weeks"
        else:
            details_text = f"Paid for {billing_qty} Days"
    elif "monthly" in p_check_lower:
        details_text = f"Paid for {billing_qty} Month" if billing_qty == 1 else f"Paid for {billing_qty} Months"
    elif "weekly" in p_check_lower:
        details_text = f"Paid for {billing_qty} Week" if billing_qty == 1 else f"Paid for {billing_qty} Weeks"
    else:
        details_text = f"Paid for {billing_qty} {p_raw_check}"

    billing_note = ""
    is_per_visit = "per visit" in shift_check_lower

    if is_per_visit:
        if visits_needed > 1 and billing_qty == 1:
            billing_note = "Next Billing will be generated after the Payment to Continue the Service."
        elif billing_qty >= visits_needed:
            billing_note = f"Paid for {visits_needed} Visits."
        elif visits_needed == 1:
            billing_note = "Paid for 1 Visit."
        elif billing_qty < visits_needed:
            billing_note = f"Next Bill will be Generated after {billing_qty} Visits."
        else:
            billing_note = details_text
    elif "month" in p_check_lower or "week" in p_check_lower:
        base_unit = "Month" if "month" in p_check_lower else "Week"
        plural_unit = base_unit + "s" if billing_qty > 1 else base_unit
        if visits_needed > 1 and billing_qty == 1:
            billing_note = "Next Billing will be generated after the Payment to Continue the Service."
        elif visits_needed > billing_qty:
            billing_note = f"Next Bill will be Generated after {billing_qty} {plural_unit}."
        else:
            billing_note = details_text
    elif "daily" in p_check_lower:
        if 1 < visits_needed < 6 and billing_qty == 1:
            billing_note = "Next Billing will be generated after the Payment to Continue the Service."
        elif billing_qty >= visits_needed:
            billing_note = f"Paid for {visits_needed} Days."
        elif visits_needed == 1:
            billing_note = "Paid for 1 Day."
        elif billing_qty < visits_needed:
            billing_note = f"Next Bill will be Generated after {billing_qty} Days."
        else:
            billing_note = details_text
    else:
        billing_note = details_text

    total_amount = unit_rate * billing_qty
    shift_map = {"12-hr Day": "12 Hours - Day", "12-hr Night": "12 Hours - Night", "24-hr": "24 Hours"}
    shift_display = shift_map.get(shift_raw_check, shift_raw_check)
    if "12" in shift_display and "Time" not in shift_display:
        shift_display += " (Time)"

    period_display = p_raw_check
    if "month" in p_check_lower:
        period_display = "Month"
    elif "week" in p_check_lower:
        period_display = "Week"
    elif "daily" in p_check_lower:
        period_display = "Day"

    unit_rate_str = "{:,.0f}".format(unit_rate)
    total_amount_str = "{:,.0f}".format(total_amount)

    if is_per_visit:
        rate_line_html = f"{shift_display} = <b>₹ {unit_rate_str}</b>"
    else:
        rate_line_html = f"{shift_display} / {period_display} = <b>₹ {unit_rate_str}</b>"

    paid_for_text = details_text

    return f"""
    <div style="text-align: right; font-size: 13px; color: #555;">
        <div style="margin-bottom: 4px;">{rate_line_html}</div>
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

# ---------------------------
# COLUMN NORMALIZATION
# ---------------------------
def normalize_columns(df: pd.DataFrame, aliases: Dict[str, List[str]]) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.strip()
    for standard_name, possible_aliases in aliases.items():
        if standard_name in df.columns:
            continue
        for alias in possible_aliases:
            for df_col in df.columns:
                if df_col.lower() == alias.lower():
                    df.rename(columns={df_col: standard_name}, inplace=True)
                    break
    return df

# ---------------------------
# IMAGE UTIL
# ---------------------------
def get_clean_image_base64(file_path: str) -> str | None:
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        img = Image.open(file_path).convert("RGBA")
        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception:
        return None

# ---------------------------
# SMALL UI HELPERS
# ---------------------------
def infer_role(plan_name: str) -> tuple:
    """
    Returns (default_role, is_locked) - minimal logic
    """
    if not plan_name:
        return "Nurse/Caregiver/Attendant", False
    if "Plan B" in plan_name:
        return "Nurse", True
    if "Plan F" in plan_name:
        return "Physiotherapist", True
    if "A-la-carte" in plan_name:
        return "Attendant", True
    return "Nurse/Caregiver/Attendant", False

def render_invoice_ui(df: pd.DataFrame, mode: str = "standard"):
    """
    Lightweight placeholder for the invoice-generation UI.
    In the original app you may have a richer implementation; we provide a safe fallback.
    """
    import streamlit as st
    st.subheader("Invoice Preview / Manager")
    if df is None or df.empty:
        st.info("No customer data loaded.")
    else:
        st.dataframe(df.head(50))

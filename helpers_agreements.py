"""
helpers_agreements.py

Helper functions for agreement generation and saving:
- Save functions for Nurse, Physio, A-la-carte agreements.
- Duplicate prevention (agreement_already_saved).
- Document hash and HTML-to-PDF conversion (WeasyPrint).
- Optional fast-indexing to an 'Agreements_Index' sheet for O(1) verification lookups.
"""

from __future__ import annotations

import datetime
import io
import hashlib
from typing import Optional, Any, Dict, List

import streamlit as st
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration


# ---------------------------
# Small utilities
# ---------------------------
def format_date_simple(d: Any) -> str:
    """
    Format a date-like object as 'DD-MM-YYYY' (no time). Returns empty string on failure.
    """
    if d is None or d == "":
        return ""
    try:
        if isinstance(d, datetime.datetime):
            d = d.date()
        if isinstance(d, datetime.date):
            return d.strftime("%d-%m-%Y")
    except Exception:
        pass
    return str(d)


def generate_doc_hash(*parts: Any) -> str:
    """
    Generate a SHA-256 based document id (hex) truncated to 16 chars.
    Deterministic for the same set of parts and fast to compute.
    """
    s = "||".join([str(p) for p in parts if p is not None])
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def convert_html_to_pdf(html: str) -> bytes:
    """
    Convert HTML string to PDF bytes using WeasyPrint.
    """
    font_config = FontConfiguration()
    pdf_io = io.BytesIO()
    HTML(string=html).write_pdf(pdf_io, font_config=font_config)
    return pdf_io.getvalue()


# ---------------------------
# Index (fast verification) helpers
# ---------------------------
def _ensure_index_sheet_in_spreadsheet(spreadsheet: Any, index_name: str = "Agreements_Index") -> Optional[Any]:
    """
    Ensure that an index worksheet named index_name exists inside the given gspread
    Spreadsheet object. If it does not exist it will be created and a header row written.
    Returns the Worksheet object or None on failure.
    NOTE: spreadsheet is expected to be a gspread.Spreadsheet object (the parent of a Worksheet).
    """
    if spreadsheet is None:
        return None
    try:
        # Try to open
        try:
            idx_ws = spreadsheet.worksheet(index_name)
        except Exception:
            # create with a safe column layout
            idx_ws = spreadsheet.add_worksheet(title=index_name, rows=1000, cols=10)
            header = ["Doc Hash", "Invoice Number", "Customer Name", "Sheet", "Saved At", "Doc Type"]
            try:
                idx_ws.append_row(header, value_input_option="USER_ENTERED")
            except Exception:
                # ignore header write failure (sheet likely empty or permission issue)
                pass
        return idx_ws
    except Exception as e:
        st.warning(f"[Index] Could not ensure index sheet: {e}")
        return None


def _append_index_row(spreadsheet: Any, doc_hash: str, invoice_no: str, customer_name: str,
                      sheet_name: str, saved_at: str, doc_type: str, index_name: str = "Agreements_Index") -> bool:
    """
    Append a single row to the index worksheet. Returns True on success.
    """
    try:
        idx_ws = _ensure_index_sheet_in_spreadsheet(spreadsheet, index_name=index_name)
        if idx_ws is None:
            return False
        row = [doc_hash, invoice_no, customer_name, sheet_name, saved_at, doc_type]
        idx_ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.warning(f"[Index] Append failed: {e}")
        return False


def verify_doc_hash_in_spreadsheet(spreadsheet: Any, doc_hash: str, index_name: str = "Agreements_Index") -> Optional[Dict[str, str]]:
    """
    Fast verification: check 'Agreements_Index' worksheet for the given doc_hash.
    Returns the first matching row as a dict with keys matching the index header, or None if not found.
    spreadsheet must be a gspread.Spreadsheet object.
    """
    if spreadsheet is None or not doc_hash:
        return None
    try:
        try:
            idx_ws = spreadsheet.worksheet(index_name)
        except Exception:
            return None
        records = idx_ws.get_all_records()
        for r in records:
            if str(r.get("Doc Hash", "")).strip() == str(doc_hash).strip():
                return {
                    "Doc Hash": r.get("Doc Hash", ""),
                    "Invoice Number": r.get("Invoice Number", ""),
                    "Customer Name": r.get("Customer Name", ""),
                    "Sheet": r.get("Sheet", ""),
                    "Saved At": r.get("Saved At", ""),
                    "Doc Type": r.get("Doc Type", "")
                }
        return None
    except Exception as e:
        st.warning(f"[Index] Verification failed: {e}")
        return None


# ---------------------------
# Duplicate check helper
# ---------------------------
def agreement_already_saved(ws: Any, invoice_no: Any, plan: Any, doc_type: Any) -> bool:
    """
    Scan the provided worksheet for an existing agreement matching invoice_no, plan, and doc_type.
    Returns True if a match is found.
    Accepts a gspread Worksheet object (ws).
    """
    if ws is None:
        return False
    try:
        records = ws.get_all_records()
    except Exception:
        # If sheet can't be read, be conservative and allow save (return False)
        return False

    doc_keys = ["Document Type", "Agreement Type", "Doc Type", "Document", "Type", "Doc_Type", "DocType"]
    invoice_keys = ["Invoice Number", "Invoice", "Invoice No.", "Invoice No", "InvoiceNumber", "Invoice_Number"]
    plan_keys = ["Plan", "Service Required", "Plan Name", "Plan"]

    inv = str(invoice_no).strip() if invoice_no is not None else ""
    plan_s = str(plan).strip() if plan is not None else ""
    dtype = str(doc_type).strip().lower() if doc_type is not None else ""

    for r in records:
        inv_val = None
        for k in invoice_keys:
            if k in r:
                inv_val = str(r.get(k, "")).strip()
                break
        plan_val = None
        for k in plan_keys:
            if k in r:
                plan_val = str(r.get(k, "")).strip()
                break
        dtype_val = None
        for k in doc_keys:
            if k in r:
                dtype_val = str(r.get(k, "")).strip().lower()
                break

        if inv_val == "" and plan_val == "" and (dtype_val is None or dtype_val == ""):
            continue

        if inv_val == inv and plan_val == plan_s and dtype_val == dtype:
            return True

    return False


# ---------------------------
# Saves (with optional index writing)
# ---------------------------
def _build_common_row(master_row: Dict[str, Any], tab5: Dict[str, Any], doc_type: str) -> List[Any]:
    """
    Build a common row skeleton (list) for saving into the sheet.
    This function centralizes column ordering to reduce mistakes.
    NOTE: Keep this in sync with your Master sheet column layout (SHEET_HEADERS in app.py).
    """
    invoice_no = master_row.get("Invoice Number", "")
    date_val = format_date_simple(master_row.get("Date", ""))
    row = [
        master_row.get("UID", ""),
        master_row.get("Serial No.", ""),
        master_row.get("Ref. No.", ""),
        invoice_no,
        date_val,
        # We'll put staff fields next (caller fills these positions as appropriate)
        # Placeholder slots:
        tab5.get("nurse_name", ""),
        tab5.get("nurse_age", ""),
        tab5.get("nurse_addr", ""),
        tab5.get("nurse_aadhar", ""),
        master_row.get("Nurse Name (Extra)", ""),
        tab5.get("nurse_age_extra", ""),
        tab5.get("nurse_addr_extra", ""),
        tab5.get("nurse_aadhar_extra", ""),
        master_row.get("Nurse Note", ""),
        master_row.get("Nurse Payment", ""),
        # Client details
        master_row.get("Customer Name", ""),
        master_row.get("Age", ""),
        master_row.get("Gender", ""),
        master_row.get("Location", ""),
        master_row.get("Address", ""),
        master_row.get("Mobile", ""),
        master_row.get("Plan", ""),
        # Document metadata placeholders (will append below)
    ]
    return row


def save_to_nurses_sheet(master_row: Dict[str, Any], tab5: Dict[str, Any], nurses_ws: Any,
                         index_name: str = "Agreements_Index") -> bool:
    """
    Save caregiver agreement to Nurses sheet. Optionally writes a small index row to the
    'Agreements_Index' sheet in the same spreadsheet for fast verification.
    Returns True on success, False otherwise.
    """
    try:
        if nurses_ws is None:
            raise Exception("Nurses worksheet unavailable")

        invoice_no = master_row.get("Invoice Number", "")
        plan = master_row.get("Plan", "")
        doc_type = master_row.get("Doc Type", master_row.get("Document Type", "Caregiver Service Agreement"))

        # Duplicate prevention (sheet-level)
        if agreement_already_saved(nurses_ws, invoice_no, plan, doc_type):
            st.warning("⚠️ Agreement already exists (Nurses). Duplicate save prevented.")
            return False

        # Build row + metadata
        row = _build_common_row(master_row, tab5, doc_type)

        # Row currently has up to Plan; append doc metadata: doc_type, saved_at, doc_hash
        saved_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_hash = generate_doc_hash(doc_type, invoice_no, master_row.get("Customer Name", ""), saved_at)

        row.extend([doc_type, saved_at, doc_hash])

        # Append to nurses_ws
        nurses_ws.append_row(row, value_input_option="USER_ENTERED")

        # Try to append to index in the parent spreadsheet for fast verification
        try:
            parent_spreadsheet = getattr(nurses_ws, "spreadsheet", None) or getattr(nurses_ws, "parent", None)
            if parent_spreadsheet:
                _append_index_row(parent_spreadsheet, doc_hash, invoice_no,
                                  master_row.get("Customer Name", ""), "Nurses", saved_at, doc_type,
                                  index_name=index_name)
        except Exception:
            # index is optional; non-fatal
            pass

        return True
    except Exception as e:
        st.error(f"Save Error (Nurses): {e}")
        return False


def save_to_physio_sheet(master_row: Dict[str, Any], tab5: Dict[str, Any], physio_ws: Any,
                         index_name: str = "Agreements_Index") -> bool:
    """
    Save caregiver (Physio) agreement to Physio sheet. Also writes to index if possible.
    """
    try:
        if physio_ws is None:
            raise Exception("Physio worksheet unavailable")

        invoice_no = master_row.get("Invoice Number", "")
        plan = master_row.get("Plan", "")
        doc_type = master_row.get("Doc Type", master_row.get("Document Type", "Caregiver Service Agreement"))

        if agreement_already_saved(physio_ws, invoice_no, plan, doc_type):
            st.warning("⚠️ Agreement already exists (Physio). Duplicate save prevented.")
            return False

        row = _build_common_row(master_row, tab5, doc_type)
        saved_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_hash = generate_doc_hash(doc_type, invoice_no, master_row.get("Customer Name", ""), saved_at)

        row.extend([doc_type, saved_at, doc_hash])

        physio_ws.append_row(row, value_input_option="USER_ENTERED")

        try:
            parent_spreadsheet = getattr(physio_ws, "spreadsheet", None) or getattr(physio_ws, "parent", None)
            if parent_spreadsheet:
                _append_index_row(parent_spreadsheet, doc_hash, invoice_no,
                                  master_row.get("Customer Name", ""), "Physio", saved_at, doc_type,
                                  index_name=index_name)
        except Exception:
            pass

        return True
    except Exception as e:
        st.error(f"Save Error (Physio): {e}")
        return False


def save_to_alacarte_sheet(master_row: Dict[str, Any], tab5: Dict[str, Any], alacarte_ws: Any,
                          index_name: str = "Agreements_Index") -> bool:
    """
    Save caregiver agreement to A-la-carte sheet. Also writes to index if possible.
    """
    try:
        if alacarte_ws is None:
            raise Exception("A-la-carte worksheet unavailable")

        invoice_no = master_row.get("Invoice Number", "")
        plan = master_row.get("Plan", "")
        doc_type = master_row.get("Doc Type", master_row.get("Document Type", "Caregiver Service Agreement"))

        if agreement_already_saved(alacarte_ws, invoice_no, plan, doc_type):
            st.warning("⚠️ Agreement already exists (A-la-carte). Duplicate save prevented.")
            return False

        row = _build_common_row(master_row, tab5, doc_type)
        saved_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_hash = generate_doc_hash(doc_type, invoice_no, master_row.get("Customer Name", ""), saved_at)

        row.extend([doc_type, saved_at, doc_hash])

        alacarte_ws.append_row(row, value_input_option="USER_ENTERED")

        try:
            parent_spreadsheet = getattr(alacarte_ws, "spreadsheet", None) or getattr(alacarte_ws, "parent", None)
            if parent_spreadsheet:
                _append_index_row(parent_spreadsheet, doc_hash, invoice_no,
                                  master_row.get("Customer Name", ""), "A-la-carte", saved_at, doc_type,
                                  index_name=index_name)
        except Exception:
            pass

        return True
    except Exception as e:
        st.error(f"Save Error (A-la-carte): {e}")
        return False

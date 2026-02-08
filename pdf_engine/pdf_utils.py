from weasyprint import HTML
import hashlib
import qrcode
import base64
from io import BytesIO

def convert_html_to_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()

def generate_doc_hash(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def generate_qr_base64(data):
    qr = qrcode.make(data)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

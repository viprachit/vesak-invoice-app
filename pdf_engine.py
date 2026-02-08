# pdf_engine.py (or paste into your utilities section)
from weasyprint import HTML, CSS
import io

DEFAULT_CSS = """
@page { size: A4; margin: 20mm; }
body { font-family: 'Lato', sans-serif; font-size: 12px; color: #111; }
"""

def convert_html_to_pdf(html_text: str, extra_css: str = None) -> bytes:
    """
    Convert HTML string to PDF bytes using WeasyPrint.
    Returns PDF bytes on success, raises exception on failure.
    """
    try:
        css = CSS(string=(DEFAULT_CSS + (extra_css or "")))
        html = HTML(string=html_text)
        out = io.BytesIO()
        html.write_pdf(out, stylesheets=[css])
        out.seek(0)
        return out.read()
    except Exception as e:
        # Re-raise, calling code should show st.error
        raise

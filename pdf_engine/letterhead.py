def render_vesak_letterhead_pdf(
    *,
    body_html,
    logo_b64,
    title,
    meta_html,
    footer_note,
    doc_hash=None,
    qr_b64=None
):
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 20mm;
    @bottom-right {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 10px;
        color: #666;
    }}
}}
body {{ font-family: Lato, sans-serif; font-size: 12px; }}
.watermark {{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    opacity: 0.04;
    z-index: -1;
}}
</style>
</head>
<body>

<div class="watermark">
    <img src="data:image/png;base64,{logo_b64}" width="300"><br>
    <div style="font-size:80px; letter-spacing:12px;">VESAK</div>
</div>

{body_html}

</body>
</html>
"""

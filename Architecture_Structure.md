backend/
├── main.py                  # App bootstrap ONLY
│
├── core/
│   ├── config.py             # settings, env, constants
│   ├── security.py           # role checks, permissions
│   └── auth.py               # current_user, later real auth
│
├── db/
│   ├── session.py            # engine, SessionLocal
│   └── models.py             # SQLAlchemy models
│
├── services/
│   ├── invoices.py           # invoice business logic
│   ├── documents.py          # future: letterhead docs
│   └── pdf.py                # ALL PDF logic (wkhtmltopdf)
│
├── routes/
│   ├── clients.py            # client routes
│   ├── invoices.py           # invoice routes
│   ├── admin.py              # admin panel routes
│   └── dashboard.py          # dashboard routes
│
├── templates/
│   ├── layout/
│   │   ├── base.html          # head, nav, shared CSS
│   │   └── print.css          # ALL print rules
│   │
│   ├── invoices/
│   │   ├── invoice.html       # invoice body ONLY
│   │   └── actions.html       # print/download buttons
│   │
│   ├── clients/
│   └── admin/
│
└── static/
    └── css/
        └── print.css          # reused by browser + PDF

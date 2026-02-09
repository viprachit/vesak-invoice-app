backend/
├── main.py
│   └─ App startup ONLY (mount routes, middleware)
│
├── core/
│   ├── auth.py
│   │   └─ Who is the current user?
│   │
│   ├── security.py
│   │   └─ Who is allowed to do what?
│   │
│   └── config.py
│       └─ Settings, env, constants
│
├── services/
│   ├── pdf.py
│   │   └─ wkhtmltopdf logic ONLY
│   │
│   ├── invoices.py
│   │   └─ Invoice business rules
│   │
│   └── documents.py
│       └─ (future) company letterhead docs
│
├── routes/
│   ├── invoices.py
│   │   └─ HTTP endpoints for invoices
│   │
│   ├── clients.py
│   ├── dashboard.py
│   └── admin.py
│
├── templates/
│   ├── layout/
│   │   ├── base.html      ← header, nav, shared CSS
│   │   └── print.css      ← ALL print rules
│   │
│   ├── invoices/
│   │   ├── invoice.html   ← invoice BODY only
│   │   └── actions.html   ← print / download buttons
│   │
│   ├── clients/
│   └── admin/
│
└── static/
    └── css/
        └── print.css      ← reused by browser + PDF

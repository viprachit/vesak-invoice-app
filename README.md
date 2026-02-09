# Vesak Invoice & Operations Platform

A secure, server-rendered internal web application for **client management, invoice generation, and official company document creation**, built with **FastAPI**, **PostgreSQL**, and **wkhtmltopdf**.

This project is designed to be:

* Fast
* Secure
* Deterministic (same input → same output)
* Easy to migrate from managed hosting to a VPS
* Safe for multi-user internal operations

---

## 🧠 What This Application Does

### Current Capabilities

* Manage client records
* View invoices using a standardized HTML template
* Generate **pixel-perfect PDFs** using `wkhtmltopdf`
* Role-aware UI (Super Admin, Operations, Viewer)
* Server-side rendering (no heavy frontend frameworks)

### Planned Capabilities

* Full admin panel with permissions
* Audit logs
* Company document generator (letterhead-based documents)
* Authentication & authorization
* VPS + Docker deployment

---

## 🏗 High-Level Architecture

The system is intentionally split into **clear layers**:

### 1. Presentation Layer (UI)

* Jinja2 templates
* Tailwind CSS
* HTMX (progressive enhancement)

Responsible only for:

* Displaying data
* Triggering backend routes

No business logic lives here.

---

### 2. Application Layer (FastAPI)

* Route handling
* Data orchestration
* Permission checks
* Template rendering
* PDF generation

This is the **brain of the system**.

---

### 3. Domain & Business Logic

* Invoice structure
* Company standards
* Document formats
* Role rules

This is where **company value** lives.

---

### 4. Infrastructure Layer

* PostgreSQL (currently Supabase, later VPS)
* wkhtmltopdf (PDF engine)
* Docker (future)
* Render (current hosting)

---

## 📁 Project Structure

```
fastapi-backend/
│
├── backend/
│   ├── main.py              # FastAPI app & routes
│   ├── db.py                # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── crud.py              # DB operations
│   ├── schemas.py           # Pydantic schemas
│   │
│   ├── utils/
│   │   ├── pdf.py            # wkhtmltopdf integration
│   │
│   ├── templates/
│   │   ├── invoice.html     # Invoice template (AS-IS)
│   │   ├── base.html
│   │   └── pages/
│   │       ├── clients/
│   │       ├── invoices/
│   │       └── dashboard.html
│
├── requirements.txt
├── .env.example
├── Dockerfile               # Used later for VPS
└── README.md
```

---

## 🧾 PDF Generation (IMPORTANT)

PDFs are generated **server-side** using:

* **wkhtmltopdf**
* Python wrapper: `pdfkit`

### Why wkhtmltopdf?

* Industry standard (banks, ERPs, accounting software)
* Pixel-perfect HTML → PDF
* Deterministic output
* Secure (no browser involvement)

### Central PDF Utility

All PDF generation is centralized in:

```
backend/utils/pdf.py
```

This ensures:

* One PDF engine
* One standard
* Easy maintenance
* No future rewrites

---

## 🔐 Roles (Current & Planned)

### Current (Temporary, Hardcoded)

* Super Admin
* Operations
* Viewer

### Planned (Auth-based)

* Super Admin
* Operations
* Viewer
* (Optional future roles)

Role logic controls:

* UI visibility
* Allowed actions
* Access to sensitive data

---

## 📄 Future Feature: Company Document Generator

This application will include a **separate document system**, distinct from invoices.

### Purpose

* Generate official company documents
* Enforce letterhead & formatting standards
* Avoid manual Word/PDF editing

### Examples

* Offer letters
* Agreements
* Internal memos
* Client notices

### Architecture (Planned)

```
templates/documents/
├── base_letterhead.html
├── offer_letter.html
├── agreement.html
```

Same PDF engine. Same reliability. Same standards.

---

## 🚀 Running Locally (Windows)

### 1. Activate virtual environment

```bat
venv\Scripts\activate
```

### 2. Install dependencies

```bat
pip install -r requirements.txt
```

### 3. Run the server

```bat
python -m uvicorn backend.main:app --reload
```

### 4. Open browser

```
http://127.0.0.1:8000
```

---

## 🐳 Containers & VPS (Planned)

The system is designed to run in **separate containers**:

* Backend API container
* Website container (optional)
* PostgreSQL container

This allows:

* Clean VPS migration
* Better security
* Independent scaling
* Easier upgrades

Docker support will be added **without changing application code**.

---

## 🧭 Roadmap

1. ✅ Invoice PDF parity (DONE)
2. ⏳ UI polish (Print / Download buttons)
3. ⏳ Company document generator
4. ⏳ Authentication & permissions
5. ⏳ Audit logs
6. ⏳ Docker + VPS migration
7. ⏳ Optional mobile-friendly UI

---

## ✨ Guiding Principles

* Stability over novelty
* Deterministic output over visual tricks
* Server-side logic over browser hacks
* Clear separation of concerns
* Easy future migration

---

## 📌 Status

This project is **actively developed** and currently in **migration phase** from Streamlit to a full FastAPI architecture.

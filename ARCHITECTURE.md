# Vesak Invoice & Operations Platform — Architecture

This document explains **how the system is structured, why it is structured this way, and how it is expected to evolve**.

It is written for:

* Future developers
* DevOps / infrastructure engineers
* System architects
* (Future) AI-assisted tooling

---

## 1. Architectural Goals

The architecture is designed with the following non-negotiable goals:

1. **Stability over novelty**
2. **Deterministic outputs** (especially PDFs)
3. **Security by default**
4. **Easy migration from managed hosting to VPS**
5. **Minimal rework as features grow**

---

## 2. System Overview

The platform is a **server-rendered internal operations system**.

There is **no heavy frontend framework** and **no browser-side business logic**.

All critical logic runs on the server.

```
Browser
  ↓
FastAPI (Application Layer)
  ↓
PostgreSQL (Data Layer)
  ↓
wkhtmltopdf (Document Engine)
```

---

## 3. Layered Architecture

### 3.1 Presentation Layer

**Responsibility:**

* Render HTML
* Capture user actions
* Minimal JavaScript (HTMX only)

**Technologies:**

* Jinja2 Templates
* Tailwind CSS
* HTMX

**Rules:**

* No database access
* No business logic
* No PDF generation

---

### 3.2 Application Layer (FastAPI)

**Responsibility:**

* Routing
* Permission checks
* Orchestration of data
* Calling PDF engine

**Key Files:**

* `backend/main.py`
* `backend/crud.py`

**Rules:**

* Knows *what* to do
* Does not decide *how documents look*

---

### 3.3 Domain & Business Logic Layer

**Responsibility:**

* Company standards
* Invoice structure
* Document formats
* Role rules

**Key Files:**

* `backend/models.py`
* `backend/utils/pdf.py`
* `backend/templates/invoice.html`

This layer is considered **high-value** and should change rarely.

---

### 3.4 Infrastructure Layer

**Responsibility:**

* Runtime environment
* Networking
* Storage
* PDF rendering binary

**Components:**

* PostgreSQL
* wkhtmltopdf
* Docker (future)
* VPS (future)

---

## 4. PDF & Document Architecture

PDF generation is **centralized** and **engine-locked**.

### PDF Engine

* wkhtmltopdf
* Python wrapper: pdfkit

### Central Rule

All PDFs must be generated **only** via:

```
backend/utils/pdf.py
```

This guarantees:

* Consistency
* Security
* Easy future upgrades

---

## 5. Invoice vs Document Separation

Invoices and company documents are **intentionally separated**.

### Invoices

* Financial records
* Client-linked
* Fixed structure

### Documents

* Internal / external communication
* Letterhead-based
* Content-driven

**They share the PDF engine but NOT templates.**

---

## 6. Role-Based Access (Conceptual)

Roles are enforced at the **application layer**.

Planned roles:

* Super Admin
* Operations
* Viewer

Rules:

* UI visibility depends on role
* Backend routes validate permissions
* PDF generation is server-controlled

---

## 7. Container & Deployment Strategy (Future)

The system is designed for **multi-container deployment**.

### Expected Containers

1. **Backend API Container**

   * FastAPI
   * wkhtmltopdf
   * PDF logic

2. **Database Container**

   * PostgreSQL

3. **Optional Website Container**

   * Public-facing site

Containers communicate over internal networking.

---

## 8. Migration Strategy

The platform supports seamless migration:

```
Render + Supabase
        ↓
Docker Compose on VPS
        ↓
(Optional) Kubernetes
```

No application code changes required.

---

## 9. Change Rules (IMPORTANT)

### Safe to change

* UI templates (non-invoice)
* Styling
* New routes

### High-risk (change carefully)

* Invoice templates
* PDF engine logic
* Database schema

---

## 10. Philosophy

This architecture prioritizes:

* Predictability
* Maintainability
* Business continuity

Over:

* Trends
* Framework churn
* Over-engineering

---

## Status

This document reflects the **current and intended architecture** of the Vesak Invoice & Operations Platform.

Any major deviation should update this file.

# Security Policy — Vesak Invoice & Operations Platform

This document describes the **security model, assumptions, and responsibilities** of the Vesak Invoice & Operations Platform.

It is written for:

* Developers
* Operators
* Auditors
* AI-assisted tooling

---

## 1. Security Philosophy

This system follows a **server-first, least-privilege, deterministic** security philosophy.

Core principles:

* No business logic in the browser
* No sensitive operations on the client
* No direct database access from UI
* No client-side PDF generation
* Predictable, auditable behavior

---

## 2. Threat Model (What We Protect Against)

The platform is designed to mitigate:

* Unauthorized data access
* Invoice tampering
* Document forgery
* Accidental data deletion
* Over-privileged users
* Browser-based attacks

---

## 3. Authentication (Planned)

Authentication will be implemented **server-side**.

Planned characteristics:

* Session or token-based auth
* Passwords stored as strong hashes
* No credentials in frontend code

Authentication logic will live in the **application layer**, not templates.

---

## 4. Authorization (Role-Based Access)

Authorization is **role-driven**.

Planned roles:

* Super Admin
* Operations
* Viewer

Rules:

* UI visibility depends on role
* Backend routes enforce permissions
* PDF generation is restricted to authorized roles

---

## 5. PDF & Document Security

All PDFs are generated:

* Server-side only
* Using wkhtmltopdf
* From trusted templates

Rules:

* No user-provided HTML
* No browser-based PDF tools
* No client-side rendering

This prevents:

* Invoice manipulation
* CSS injection
* Client-side tampering

---

## 6. Data Storage Security

* Database access is server-only
* Credentials stored in environment variables
* No secrets committed to repository

Planned improvements:

* Encrypted backups
* Audit trails
* Access logging

---

## 7. Deployment Security

Current:

* Managed hosting
* Isolated database

Future (VPS):

* Docker container isolation
* Network-level separation
* Non-root containers

---

## 8. Change Control

High-risk changes include:

* Invoice templates
* PDF engine logic
* Database schema

Such changes must be:

* Reviewed
* Tested
* Documented

---

## 9. Incident Response (Planned)

In case of security incidents:

* Access will be revoked
* Logs reviewed
* Affected data identified
* Root cause documented

---

## 10. Status

This document reflects the **current and intended security posture** of the platform.

Any security-related change should update this file.

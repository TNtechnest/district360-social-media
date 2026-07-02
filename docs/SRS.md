# District360 — Software Requirements Specification (SRS)

**Version:** 1.0  
**Status:** Draft for technical review  
**Audience:** Engineers, QA, architects, business analysts

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional software requirements for District360, a multi-tenant district governance and service delivery platform.

### 1.2 Scope

The SRS covers the web application, backend services, database, APIs, and integrations required for Phase 1 of District360.

### 1.3 Definitions

| Term | Definition |
|------|------------|
| Tenant | A logical district instance within the platform |
| Ward | Subdivision of a district |
| SLA | Service Level Agreement for request resolution |
| RLS | Row-Level Security in PostgreSQL |
| PWA | Progressive Web Application |

---

## 2. System Overview

District360 is a cloud-native SaaS application with a React/Next.js frontend, Node.js backend microservices, PostgreSQL database, Redis cache, and object storage. It supports multiple districts with strict data isolation.

---

## 3. Functional Requirements

### 3.1 Authentication & Authorization

- SRS-AU-01: The system shall support OAuth 2.0 / OpenID Connect login.
- SRS-AU-02: The system shall support phone OTP login.
- SRS-AU-03: The system shall enforce RBAC at the API gateway level.
- SRS-AU-04: The system shall issue JWT access tokens (15 min expiry) and refresh tokens (7 days).
- SRS-AU-05: The system shall support MFA for admin roles.

### 3.2 Tenant Management

- SRS-TM-01: Super Admins shall be able to create, suspend, and delete tenants.
- SRS-TM-02: Tenant configuration shall include name, slug, timezone, locale, and branding.
- SRS-TM-03: The system shall enforce tenant data isolation using `district_id` and RLS.

### 3.3 User Management

- SRS-UM-01: District Admins shall be able to invite users and assign roles.
- SRS-UM-02: Users shall belong to exactly one tenant.
- SRS-UM-03: Users may have multiple roles (e.g., Officer + Field Worker).

### 3.4 Service Request Module

- SRS-SR-01: Citizens shall create requests with title, description, category, location (GPS/address), and attachments.
- SRS-SR-02: The system shall auto-assign requests based on category → department → ward.
- SRS-SR-03: Request statuses shall follow: `Draft → Submitted → Acknowledged → In Progress → Resolved → Closed`.
- SRS-SR-04: Citizens shall receive status updates via their preferred channel.
- SRS-SR-05: The system shall enforce SLA timers and escalate breached requests.

### 3.5 Department & Workflow

- SRS-DW-01: District Admins shall configure departments and service categories.
- SRS-DW-02: Department Heads shall define workflow stages and SLA rules.
- SRS-DW-03: The system shall support custom forms per service category.

### 3.6 Field Operations

- SRS-FO-01: Field Workers shall view assigned tasks on a mobile-optimized interface.
- SRS-FO-02: Field Workers shall upload geotagged photos and voice notes.
- SRS-FO-03: Field Workers shall mark tasks complete with a digital signature or OTP verification from citizen.

### 3.7 Payments

- SRS-PY-01: The system shall integrate with payment gateways for service fees and taxes.
- SRS-PY-02: Citizens shall view payment history and download receipts.
- SRS-PY-03: Finance officers shall reconcile payments via reports.

### 3.8 Notifications

- SRS-NF-01: The system shall support email, SMS, push, and in-app notifications.
- SRS-NF-02: Users shall configure notification preferences.
- SRS-NF-03: Notification templates shall be tenant-configurable.

### 3.9 Audit & Reporting

- SRS-AR-01: The system shall log all create, update, and delete actions with actor, timestamp, and IP.
- SRS-AR-02: Auditors shall export audit logs in CSV/PDF.
- SRS-AR-03: Dashboards shall display SLA, workload, and satisfaction metrics.

---

## 4. Use Cases

### UC-01: Citizen Registers on Platform

**Actor:** Citizen  
**Precondition:** Citizen has a valid email or phone number.  
**Flow:**
1. Citizen visits district portal.
2. Selects sign-up and provides email/phone.
3. System sends OTP or verification link.
4. Citizen verifies identity and completes profile.
5. System creates user in tenant.

**Postcondition:** Citizen can log in and raise requests.

---

### UC-02: Citizen Raises a Service Request

**Actor:** Citizen  
**Precondition:** Citizen is authenticated.  
**Flow:**
1. Citizen selects service category.
2. Fills description and location.
3. Uploads optional photos.
4. Submits request.
5. System validates and auto-routes to department/ward.
6. Citizen receives acknowledgment with tracking ID.

**Postcondition:** Request is in `Submitted` status.

---

### UC-03: Department Officer Processes Request

**Actor:** Department Officer  
**Precondition:** Officer is authenticated and request is assigned.  
**Flow:**
1. Officer views assigned queue.
2. Opens request and reviews details.
3. Updates status to `In Progress`.
4. Adds internal notes or requests citizen clarification.
5. Assigns to Field Worker if field visit required.

**Postcondition:** Request progresses through workflow.

---

### UC-04: Field Worker Resolves On-Site Task

**Actor:** Field Worker  
**Precondition:** Task is assigned to field worker.  
**Flow:**
1. Worker logs in via mobile web.
2. Views task list and navigates to location.
3. Checks in with GPS.
4. Performs work and uploads before/after photos.
5. Marks task resolved.
6. Citizen receives notification to confirm/feedback.

**Postcondition:** Task status updated; request moves to `Resolved`.

---

### UC-05: District Admin Onboards a Department

**Actor:** District Admin  
**Precondition:** Admin is authenticated.  
**Flow:**
1. Admin navigates to department management.
2. Creates department with name, head, ward mapping.
3. Defines service categories and SLA rules.
4. Invites department users.

**Postcondition:** Department can receive and process requests.

---

### UC-06: Super Admin Provisions New District

**Actor:** Super Admin  
**Precondition:** Platform is operational.  
**Flow:**
1. Super Admin enters district details.
2. System creates tenant, default roles, and sample data.
3. Invites District Admin.
4. District Admin completes configuration.

**Postcondition:** District is live on the platform.

---

### UC-07: Auditor Reviews Compliance Report

**Actor:** Auditor  
**Precondition:** Auditor has read-only access.  
**Flow:**
1. Auditor selects reporting period and district.
2. System generates SLA, audit, and financial summary.
3. Auditor exports report.

**Postcondition:** Compliance report is exported.

---

### UC-08: Citizen Makes Online Payment

**Actor:** Citizen  
**Precondition:** Citizen has an outstanding bill/fee.  
**Flow:**
1. Citizen views pending payments.
2. Selects payment and gateway.
3. Completes payment on gateway.
4. Gateway notifies District360.
5. System updates payment status and issues receipt.

**Postcondition:** Payment recorded; receipt available.

---

## 5. Interface Requirements

### 5.1 User Interfaces

- Responsive web UI supporting desktop, tablet, and mobile.
- PWA capabilities for field worker offline resilience (Phase 2).
- WCAG 2.1 AA accessibility.

### 5.2 APIs

- RESTful JSON APIs documented with OpenAPI 3.0.
- Standard HTTP methods and status codes.
- Pagination, filtering, sorting, and search on list endpoints.

### 5.3 Integrations

- Payment gateway (Stripe/Razorpay/region-specific)
- SMS gateway (Twilio/MSG91/region-specific)
- Email service (SendGrid/AWS SES)
- Government identity providers (OAuth/OIDC)
- GIS/mapping service (Google Maps / Mapbox / OpenStreetMap)

---

## 6. Non-Functional Requirements

See [BRD.md](./BRD.md) Section 6 for business-aligned NFRs. Additional technical NFRs:

- The API layer shall be stateless to support horizontal scaling.
- The database shall support read replicas for reporting workloads.
- File uploads shall be virus-scanned and size-limited.
- All secrets shall be stored in a secrets manager (e.g., AWS Secrets Manager, Vault).

---

## 7. Constraints

- Must comply with local data residency laws.
- Must support UTF-8 and regional languages.
- Must run on cloud infrastructure with no on-premise dependency in Phase 1.

---

## 8. Traceability Matrix

| Requirement | Use Case | Status |
|-------------|----------|--------|
| SRS-AU-01 | UC-01 | Planned |
| SRS-TM-01 | UC-06 | Planned |
| SRS-SR-01 | UC-02 | Planned |
| SRS-SR-03 | UC-03 | Planned |
| SRS-FO-01 | UC-04 | Planned |
| SRS-DW-01 | UC-05 | Planned |
| SRS-AR-01 | UC-07 | Planned |
| SRS-PY-01 | UC-08 | Planned |

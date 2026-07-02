# District360 — Architecture Document

**Version:** 1.0  
**Status:** Draft for technical review  
**Audience:** Architects, engineers, DevOps, security reviewers

---

## 6. System Architecture

District360 follows a modular, cloud-native, multi-tenant architecture. The system is composed of loosely coupled services communicating via HTTP REST and asynchronous events.

### 6.1 High-Level Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Citizen Web │  │ Admin Portal │  │ Field Worker Mobile Web  │  │
│  │  (Next.js)   │  │  (Next.js)   │  │    (PWA / Next.js)       │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘  │
└─────────┼─────────────────┼──────────────────────┼─────────────────┘
          │                 │                      │
          └─────────────────┼──────────────────────┘
                            │ HTTPS / WSS
┌───────────────────────────▼─────────────────────────────────────────┐
│                         EDGE LAYER                                  │
│   CDN (Static Assets)  │  WAF  │  Load Balancer  │  API Gateway     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      APPLICATION LAYER                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │  Identity   │ │   Tenant    │ │   Request   │ │ Notification │  │
│  │  Service    │ │  Service    │ │  Service    │ │   Service    │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │  Payment    │ │   Report    │ │   File      │ │   Workflow   │  │
│  │  Service    │ │  Service    │ │  Service    │ │   Engine     │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                       DATA LAYER                                    │
│  PostgreSQL (Primary)  │  Redis (Cache/Queue)  │  Object Storage   │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Service Descriptions

| Service | Responsibility | Tech |
|---------|---------------|------|
| Identity Service | Auth, users, roles, sessions | Node.js / NestJS |
| Tenant Service | District provisioning, config | Node.js / NestJS |
| Request Service | Service request lifecycle | Node.js / NestJS |
| Workflow Engine | SLA, routing, escalations | Node.js / Temporal / BullMQ |
| Notification Service | Multi-channel messaging | Node.js / NestJS |
| Payment Service | Billing, receipts, reconciliation | Node.js / NestJS |
| Report Service | Analytics and exports | Node.js / PostgreSQL |
| File Service | Uploads, scans, storage | Node.js / NestJS |

### 6.3 Communication Patterns

- **Synchronous:** REST API for user-facing operations.
- **Asynchronous:** Event bus (Redis Pub/Sub or message queue) for notifications, audit, workflows, and webhooks.

---

## 9. API Architecture

### 9.1 API Style

- RESTful JSON APIs.
- OpenAPI 3.0 specification published at `/api/docs`.
- Versioned URL paths: `/api/v1/...`.

### 9.2 Cross-Cutting API Concerns

| Concern | Implementation |
|---------|---------------|
| Authentication | JWT Bearer tokens in `Authorization` header |
| Tenant scoping | `X-District-ID` header or inferred from JWT |
| Pagination | `?page=1&limit=20` with `Link` headers or meta object |
| Filtering | `?status=open&ward=north` |
| Sorting | `?sort=-created_at` |
| Search | `?q=keyword` |
| Rate limiting | 100 req/min per user, 1000 req/min per service account |
| Idempotency | `Idempotency-Key` header for POST/PUT |

### 9.3 Sample Endpoints

```http
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/otp/send
POST   /api/v1/auth/otp/verify

GET    /api/v1/districts
POST   /api/v1/districts
GET    /api/v1/districts/:id

GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/:id
PATCH  /api/v1/users/:id

GET    /api/v1/requests
POST   /api/v1/requests
GET    /api/v1/requests/:id
PATCH  /api/v1/requests/:id/status
POST   /api/v1/requests/:id/comments
POST   /api/v1/requests/:id/attachments

GET    /api/v1/reports/dashboard
GET    /api/v1/reports/audit
POST   /api/v1/payments
GET    /api/v1/payments/:id/receipt
```

### 9.4 Event Schema

Events are published on tenant-scoped channels:

```json
{
  "event": "request.created",
  "tenant_id": "dist_abc123",
  "timestamp": "2026-06-23T10:00:00Z",
  "payload": { "request_id": "req_xyz789", "category": "water" }
}
```

---

## 10. Folder Structure

```
district360/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
├── apps/
│   ├── web/                    # Next.js citizen/admin/field portals
│   │   ├── src/
│   │   │   ├── app/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── lib/
│   │   │   ├── stores/
│   │   │   └── styles/
│   │   ├── public/
│   │   └── package.json
│   └── api/                    # Backend services monorepo
│       ├── src/
│       │   ├── identity/
│       │   ├── tenant/
│       │   ├── request/
│       │   ├── workflow/
│       │   ├── notification/
│       │   ├── payment/
│       │   ├── report/
│       │   ├── file/
│       │   ├── common/
│       │   └── main.ts
│       └── package.json
├── packages/
│   ├── shared/                 # Shared types, constants, utilities
│   ├── ui/                     # Shared UI component library
│   ├── config/                 # ESLint, TS, Tailwind configs
│   └── database/               # Prisma schema, migrations, seeds
├── docs/
│   ├── BRD.md
│   ├── SRS.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   └── ROADMAP.md
├── infra/
│   ├── docker/
│   ├── k8s/
│   ├── terraform/
│   └── scripts/
├── tests/
│   ├── e2e/
│   ├── integration/
│   └── load/
├── PROJECT_STATE.md
├── turbo.json
├── pnpm-workspace.yaml
├── docker-compose.yml
└── README.md
```

---

## 11. Security Architecture

### 11.1 Defense in Depth

| Layer | Controls |
|-------|----------|
| Network | TLS 1.3, WAF, DDoS protection, private subnets |
| Application | Input validation, parameterized queries, CSRF protection, CORS |
| Authentication | OAuth 2.0 / OIDC, JWT, MFA for admins, session expiry |
| Authorization | RBAC, ABAC for sensitive data, tenant isolation |
| Data | Encryption at rest (AES-256), encryption in transit (TLS) |
| Database | RLS policies, least-privilege DB users, audit logging |
| Secrets | Secrets manager, no hardcoded credentials, credential rotation |
| Operations | Container scanning, dependency checks, security patches |

### 11.2 Tenant Isolation

- Application layer always injects `district_id` from JWT claims.
- PostgreSQL RLS policies block cross-tenant reads/writes.
- Object storage paths prefixed by tenant ID.
- Background jobs validated against tenant scope.

### 11.3 Data Privacy

- Consent capture during registration.
- Data retention policies per tenant configuration.
- Right to access and delete personal data (GDPR/local law).
- PII masked in logs and read-only exports.

### 11.4 Audit & Compliance

- Immutable audit log table.
- Log actor, action, resource, tenant, IP, user agent, timestamp.
- Audit logs retained for 7 years.

---

## 12. Deployment Architecture

### 12.1 Environments

| Environment | Purpose |
|-------------|---------|
| Local | Developer workstations via Docker Compose |
| Dev | Feature integration, automated deployments |
| Staging | Pre-production validation |
| Production | Live tenant workloads |

### 12.2 Infrastructure Stack

| Component | Choice |
|-----------|--------|
| Container orchestration | Kubernetes (EKS / AKS / GKE) |
| Ingress | NGINX Ingress Controller + Cert Manager |
| Service mesh | Optional: Istio for mTLS (Phase 2) |
| Database | PostgreSQL 16+ with read replicas |
| Cache/Queue | Redis Cluster |
| Object storage | S3-compatible (AWS S3 / MinIO) |
| Secrets | AWS Secrets Manager or HashiCorp Vault |
| CI/CD | GitHub Actions |
| Monitoring | Prometheus + Grafana + Loki |
| APM | OpenTelemetry / Jaeger |

### 12.3 Deployment Flow

1. Developer pushes to feature branch.
2. GitHub Actions runs lint, unit tests, integration tests.
3. On PR merge to `main`, build container images and push to registry.
4. Staging deployment triggered automatically.
5. Production deployment gated by manual approval and smoke tests.

### 12.4 Scaling Strategy

- Horizontal Pod Autoscaling (HPA) based on CPU/memory/custom metrics.
- Read replicas for reporting queries.
- CDN for static assets and file downloads.
- Database connection pooling via PgBouncer.

---

## 13. UI/UX Architecture

### 13.1 Design Principles

- **Mobile-first:** Field workers and citizens primarily use mobile devices.
- **Accessible:** WCAG 2.1 AA compliance.
- **Consistent:** Shared design system and component library.
- **Localizable:** RTL/LTR and multi-language support.
- **Performant:** Code splitting, lazy loading, edge caching.

### 13.2 Portal Structure

| Portal | Primary Users | Key Screens |
|--------|---------------|-------------|
| Citizen Portal | Citizens, guests | Home, services, request form, tracking, payments, profile |
| Admin Portal | District/Department admins | Dashboards, user management, config, reports |
| Field Portal | Field workers | Task list, map view, check-in, photo upload |

### 13.3 Tech Stack

- **Framework:** Next.js 14+ (App Router)
- **Styling:** Tailwind CSS
- **Components:** Radix UI / Shadcn UI
- **State:** Zustand + React Query (TanStack Query)
- **Forms:** React Hook Form + Zod
- **Maps:** Mapbox / Leaflet
- **Charts:** Recharts / Tremor

### 13.4 User Flow — Citizen Request

```text
Home → Select Service → Fill Form + Location → Submit → Tracking Page → Updates/Feedback
```

### 13.5 Component Hierarchy

```text
App Shell
├── Layout (Header, Sidebar, Footer)
├── Pages
│   ├── Public Pages
│   ├── Auth Pages
│   └── Protected Pages
│       ├── Dashboard
│       ├── Request Module
│       ├── Admin Modules
│       └── Field Module
└── Shared Components
    ├── Data Tables
    ├── Forms
    ├── Maps
    └── Charts
```

---

## 14. Technology Summary

| Layer | Technology |
|-------|------------|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Node.js, NestJS, TypeScript |
| Database | PostgreSQL 16, Prisma ORM |
| Cache/Queue | Redis, BullMQ |
| Search | PostgreSQL full-text / Elasticsearch (Phase 2) |
| File Storage | S3-compatible object storage |
| Messaging | SMS gateway, email service, Firebase Cloud Messaging |
| Payments | Stripe / Razorpay / regional gateway |
| Identity | OAuth2/OIDC provider, Keycloak/Auth0 option |
| DevOps | Docker, Kubernetes, Terraform, GitHub Actions |
| Monitoring | Prometheus, Grafana, Loki, OpenTelemetry |

---

## 15. Architecture Decision Records

### ADR-001: Shared Database, Tenant-Aware Isolation

**Decision:** Use a single PostgreSQL database with `district_id` columns and RLS for tenant isolation.  
**Rationale:** Lower operational cost, simpler backups, easier schema migrations.  
**Trade-off:** Must rigorously enforce `district_id` scoping in every query.

### ADR-002: Monorepo with Turborepo

**Decision:** Use a pnpm/Turborepo monorepo for web and API apps plus shared packages.  
**Rationale:** Shared types, single CI pipeline, consistent tooling.  
**Trade-off:** Requires discipline in package boundaries.

### ADR-003: API Gateway for Cross-Cutting Concerns

**Decision:** Use an API gateway (Kong/NGINX) for auth, rate limiting, and routing.  
**Rationale:** Centralizes security and observability.  
**Trade-off:** Adds a network hop; must avoid business logic in gateway.

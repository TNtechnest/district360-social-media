# District360 — Database Architecture

**Version:** 1.0  
**Status:** Draft for technical review  
**Audience:** Backend engineers, DBAs, architects

---

## 7. Database Architecture

### 7.1 Database Choice

District360 uses **PostgreSQL 16+** as the primary relational database. PostgreSQL provides:

- ACID compliance for transactional workflows.
- Native JSONB support for flexible form data.
- PostGIS extension for geospatial queries.
- Row-Level Security (RLS) for tenant isolation.
- Robust full-text search (optionally augmented by Elasticsearch in Phase 2).

### 7.2 Tenant Isolation Strategy

- **Shared database, tenant-aware schema.**
- Every tenant-scoped table includes `district_id UUID NOT NULL`.
- RLS policies enforce that users only access rows where `district_id` matches their tenant.
- Application services retrieve `district_id` from JWT claims and apply it to all queries.

### 7.3 Schema Organization

| Schema | Purpose |
|--------|---------|
| `public` | Shared lookup tables, migrations metadata |
| `tenant` | Tenant configuration and global admin data |
| `identity` | Users, roles, permissions, sessions |
| `service` | Service requests, workflows, SLAs |
| `payment` | Transactions, invoices, receipts |
| `notification` | Templates, delivery logs, preferences |
| `audit` | Immutable audit logs |

### 7.4 Scaling Strategy

- Read replicas for analytics and reporting workloads.
- Connection pooling via PgBouncer.
- Partitioning for large audit and notification tables by time range.
- Indexing on `district_id`, status, created_at, and geospatial columns.

---

## 8. ER Diagram

```mermaid
erDiagram
    DISTRICT ||--o{ USER : has
    DISTRICT ||--o{ DEPARTMENT : contains
    DISTRICT ||--o{ SERVICE_CATEGORY : defines
    DISTRICT ||--o{ SERVICE_REQUEST : receives
    DISTRICT ||--o{ PAYMENT : records
    DISTRICT ||--o{ AUDIT_LOG : generates

    USER ||--o{ USER_ROLE : has
    ROLE ||--o{ USER_ROLE : assigned_to
    ROLE ||--o{ ROLE_PERMISSION : has
    PERMISSION ||--o{ ROLE_PERMISSION : granted_to

    USER ||--o{ SERVICE_REQUEST : creates
    USER ||--o{ REQUEST_ASSIGNMENT : assigned
    USER ||--o{ REQUEST_COMMENT : writes
    USER ||--o{ PAYMENT : makes
    USER ||--o{ NOTIFICATION : receives

    DEPARTMENT ||--o{ SERVICE_CATEGORY : owns
    DEPARTMENT ||--o{ USER : employs
    SERVICE_CATEGORY ||--o{ SERVICE_REQUEST : categorizes
    WORKFLOW ||--o{ SERVICE_CATEGORY : governs

    SERVICE_REQUEST ||--o{ REQUEST_ASSIGNMENT : has
    SERVICE_REQUEST ||--o{ REQUEST_COMMENT : contains
    SERVICE_REQUEST ||--o{ REQUEST_ATTACHMENT : includes
    SERVICE_REQUEST ||--o{ PAYMENT : charges
    SERVICE_REQUEST ||--o{ SLA_EVENT : tracks

    NOTIFICATION_TEMPLATE ||--o{ NOTIFICATION : uses

    DISTRICT {
        uuid id PK
        string name
        string slug UK
        string region
        jsonb config
        string status
        timestamp created_at
        timestamp updated_at
    }

    USER {
        uuid id PK
        uuid district_id FK
        string email UK
        string phone UK
        string full_name
        string password_hash
        string auth_provider
        string status
        timestamp created_at
        timestamp updated_at
    }

    ROLE {
        uuid id PK
        uuid district_id FK
        string name
        string description
        boolean is_system
    }

    USER_ROLE {
        uuid user_id FK
        uuid role_id FK
        uuid district_id FK
    }

    PERMISSION {
        uuid id PK
        string resource
        string action
        string description
    }

    ROLE_PERMISSION {
        uuid role_id FK
        uuid permission_id FK
    }

    DEPARTMENT {
        uuid id PK
        uuid district_id FK
        string name
        string code
        jsonb wards
        uuid head_id FK
    }

    SERVICE_CATEGORY {
        uuid id PK
        uuid district_id FK
        uuid department_id FK
        string name
        string description
        jsonb form_schema
        uuid workflow_id FK
    }

    WORKFLOW {
        uuid id PK
        uuid district_id FK
        string name
        jsonb stages
        jsonb sla_rules
    }

    SERVICE_REQUEST {
        uuid id PK
        uuid district_id FK
        uuid citizen_id FK
        uuid category_id FK
        uuid department_id FK
        string title
        text description
        string status
        jsonb location
        jsonb custom_data
        timestamp sla_due_at
        timestamp resolved_at
        timestamp created_at
        timestamp updated_at
    }

    REQUEST_ASSIGNMENT {
        uuid id PK
        uuid request_id FK
        uuid assignee_id FK
        string role
        timestamp assigned_at
        timestamp completed_at
    }

    REQUEST_COMMENT {
        uuid id PK
        uuid request_id FK
        uuid author_id FK
        text content
        boolean is_internal
        timestamp created_at
    }

    REQUEST_ATTACHMENT {
        uuid id PK
        uuid request_id FK
        uuid uploaded_by FK
        string file_url
        string file_type
        timestamp created_at
    }

    SLA_EVENT {
        uuid id PK
        uuid request_id FK
        string event_type
        timestamp occurred_at
        jsonb metadata
    }

    PAYMENT {
        uuid id PK
        uuid district_id FK
        uuid request_id FK
        uuid payer_id FK
        decimal amount
        string currency
        string status
        string gateway_reference
        jsonb gateway_response
        timestamp paid_at
        timestamp created_at
    }

    NOTIFICATION_TEMPLATE {
        uuid id PK
        uuid district_id FK
        string event_key
        string channel
        string subject
        text body
    }

    NOTIFICATION {
        uuid id PK
        uuid district_id FK
        uuid user_id FK
        uuid template_id FK
        string channel
        string status
        jsonb payload
        timestamp sent_at
        timestamp created_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid district_id FK
        uuid actor_id FK
        string action
        string resource_type
        uuid resource_id
        jsonb before_state
        jsonb after_state
        string ip_address
        string user_agent
        timestamp created_at
    }
```

---

## 9. Table Descriptions

### 9.1 `district`

Stores each tenant. The `config` JSONB holds branding, locale, timezone, and feature flags.

### 9.2 `user`

Stores user accounts. Users are scoped to a single district. Authentication can be local, OAuth, or OTP-based.

### 9.3 `role` / `user_role` / `permission` / `role_permission`

RBAC model. Roles are tenant-specific but seeded from system templates. Permissions are global actions on resources.

### 9.4 `department`

Departments within a district. `wards` JSONB defines the wards/zones the department serves.

### 9.5 `service_category`

Categories of citizen services. Includes a JSONB `form_schema` for dynamic request forms and a reference to a workflow.

### 9.6 `workflow`

Defines status stages and SLA rules per category.

### 9.7 `service_request`

Core entity. Tracks citizen requests, status, location, custom form data, and SLA due date.

### 9.8 `request_assignment`

Links requests to officers or field workers, tracking assignment and completion.

### 9.9 `request_comment`

Threaded comments; `is_internal` separates staff notes from citizen-visible updates.

### 9.10 `request_attachment`

References uploaded files stored in object storage.

### 9.11 `sla_event`

Records SLA milestones and breaches for reporting.

### 9.12 `payment`

Records online payments linked to requests or general fees.

### 9.13 `notification` / `notification_template`

Message delivery tracking and tenant-customizable templates.

### 9.14 `audit_log`

Immutable record of all significant data changes.

---

## 10. Indexing Strategy

| Table | Indexes |
|-------|---------|
| `district` | `slug` (unique), `status` |
| `user` | `district_id + email`, `district_id + phone`, `status` |
| `service_request` | `district_id + status`, `district_id + created_at`, `district_id + category_id`, GIST on `location` |
| `request_assignment` | `request_id`, `assignee_id`, `assigned_at` |
| `payment` | `district_id + status`, `gateway_reference` |
| `notification` | `district_id + user_id + status`, `created_at` |
| `audit_log` | `district_id + created_at`, `resource_type + resource_id` |

---

## 11. Partitioning Strategy

- `audit_log`: Range partition by `created_at` (monthly).
- `notification`: Range partition by `created_at` (monthly).
- This improves query performance and simplifies archival of old records.

---

## 12. Backup & Recovery

- Daily automated snapshots with point-in-time recovery.
- Cross-region replication for disaster recovery.
- Quarterly restore drills.

---

## 13. Migration & Seeding

- Database migrations managed with Prisma Migrate or Flyway.
- Seed scripts create system permissions, default role templates, and sample workflows.
- New tenant provisioning applies tenant-specific seeds programmatically.

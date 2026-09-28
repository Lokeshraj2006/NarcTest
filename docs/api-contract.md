# API Contract — FieldProof

> Full OpenAPI spec is auto-generated at `/docs` when the backend runs.
> This document summarises the planned endpoints and their contracts.

## Base URL

- Local: `http://localhost:8000`
- Production: `https://fieldproof-api-<hash>.run.app`

---

## Endpoints (planned)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | Public | Register new user |
| `POST` | `/auth/login` | Public | Login, get JWT |
| `GET`  | `/health` | Public | Liveness probe |
| `POST` | `/evidence/upload` | Inspector+ | Upload evidence (image+GPS+timestamp) |
| `POST` | `/compliance/check` | Inspector+ | Run compliance check on evidence |
| `GET`  | `/compliance/{product_id}` | Inspector+ | Get compliance status |
| `POST` | `/complaints` | Consumer+ | File a consumer complaint |
| `GET`  | `/inspections` | Inspector+ | List inspections |
| `POST` | `/violations/{id}/confirm` | Admin | Confirm a violation |
| `POST` | `/violations/{id}/penalty` | Admin | Assign penalty |
| `GET`  | `/legal-notice/{id}` | Admin | Download legal notice PDF |

---

## Authentication

All protected endpoints require `Authorization: Bearer <JWT>` header.

### Roles (RBAC)
- **consumer** — file complaints, view own complaint status
- **inspector** — upload evidence, run compliance checks, view inspections
- **admin** — confirm violations, assign penalties, generate legal notices

---

## Request/Response Schemas

Detailed schemas will be documented per-endpoint in subsequent deliverables.
Refer to `/docs` (Swagger UI) for the live, auto-generated OpenAPI spec.

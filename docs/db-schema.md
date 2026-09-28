# Database Schema — FieldProof

> Detailed ERD and column definitions will be added with Deliverable 2 (models + migrations).

## Planned Tables

| Table | Purpose |
|-------|---------|
| `users` | App users with role (admin/inspector/consumer), bcrypt password hash |
| `products` | Registered products with label metadata |
| `evidence_records` | Uploaded images with SHA-256 hash, GPS, NTP-verified timestamp |
| `inspections` | Inspection sessions linking inspector → products → evidence |
| `complaints` | Consumer-filed complaints against products |
| `rule_checks` | Individual rule check results (13 per compliance run) |
| `violation_reports` | Confirmed violations with inspector notes |
| `penalties` | Legal penalty records (amount, section, status) |
| `legal_notices` | Generated PDF legal notices |
| `calibration_records` | Barcode → mm scale factor per evidence image |
| `font_size_rules` | Statutory minimum font size table (reference data) |

## Relationships

```
users ─┬─< inspections ──< evidence_records
       │                  └──< calibration_records
       ├─< complaints
       └─< violation_reports ──< penalties
                               └──< legal_notices

products ──< inspections
          └──< complaints
          └──< rule_checks
```

Detailed column-level schema will be documented alongside Alembic migrations.

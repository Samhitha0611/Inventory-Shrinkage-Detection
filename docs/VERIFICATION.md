# Verification results

Verified 15 November 2026 against the full synthetic dataset, seed 20261022.

- 100 stores; 5,000 SKUs; 1,000,000 movements; 20,000 cycle counts.
- Full validator: PASS, 85 recorded checks, zero unexpected errors and zero absent structural exceptions.
- Negative running stock: zero. Count as-of reconciliation failures: zero. Unexpected shift-time or role-authorization failures: zero.
- Independently detected anomaly records: 4652; false positives: 0; false negatives: 0.
- Synthetic precision: 100.0%; recall: 100.0%; F1: 1.000.
- Per-issue coverage: missing adjustment reason, wrong-store/shift mismatch, transfer double debit, repeated adjustments, unexplained count shortage, and count-before-reference.
- All explicit benign damage and return examples have zero false positives.
- Two isolated full-scale regenerations produced matching row counts and SHA-256 checksums for every CSV; both match the active full dataset manifest.
- 30 automated tests passed: 15 pipeline, 11 workflow/filtering, and 4 Streamlit interaction tests. Coverage includes absent ground truth, unlabelled anomalies, persistent reassignment/closure, append-only history, stale/concurrent writes, filters, and required closure notes.
- Real headless Edge checks passed against the full dataset: reason filtering, CSV/JSON downloads, OPEN -> IN_PROGRESS -> CLOSED, closure notes and history export. Screenshots use a temporary workflow database; user case history remains unchanged.
- Reference SQLite schema executes successfully.

The structural exceptions are deliberately retained in the operational evidence. PASS requires that exact planted exceptions are present and separately reported; it does not claim these records are valid baseline transactions. Evaluation scores describe a controlled synthetic benchmark, not real-world accuracy.

Machine-readable reports: data/generated/validation_summary.json, evaluation_report.json, reproducibility_check.json and manifest.json.

The bundled starter sample also passes validation, evaluation and isolated two-run reproducibility. The field dictionary covers 109 fields across 13 exported tables (including ground truth) and three live persistence tables. The submission archive contains source, tests, documentation, screenshots, the linked sample and full-run evidence; it excludes live databases and full-size CSVs.

# Project report

## Problem and objective

Detect unusual inventory loss by comparing receipts, sales, transfers, adjustments, returns and cycle counts. The result must show evidence, distinguish legitimate operational loss, preserve investigation history and support measurable evaluation.

## Solution

A fixed-seed generator creates linked master data, opening balances, inventory events, physical counts and labelled exceptions. An independent rule engine reads operational evidence without labels. An indexed SQLite scratch validator checks relationships, arithmetic, time ordering and lifecycle consistency. Evaluation compares predictions with a separate ground-truth sidecar. A Streamlit dashboard supports filtering, evidence review, exports and persistent investigations.

## Coverage

- Master entities: Store, SKU, EmployeeRole, Shift and Promotion.
- Operational entities: StoreSKUOpeningBalance, InventoryMovement, CycleCount and Return.
- Decision entities: ShrinkageAlert, Investigation and append-only InvestigationEvent.
- Live review storage: namespaced SQLite snapshots plus append-only audit records.
- Full volume: 100 stores, 5,000 SKUs, 1,000,000 movements and 20,000 counts. The bundled starter sample has 10 stores, 100 SKUs, 10,000 movements and 500 counts.
- Planted scenarios: wrong-store/shift association, missing adjustment reason, double-debit transfer, repeated negative adjustments, unexplained count shortage and count-before-reference timing.
- Benign coverage: documented damage, sellable returns, receipts, sales and valid transfers.

## Decisions and traceability

Expected stock is derived from the ledger at the count timestamp. Unavailable outgoing stock is handled with explicit replenishment; balances are never silently clamped. Every alert records its source IDs and conflicting values. Exposed value uses affected units times cost; it is a review estimate, not confirmed loss. Investigation closure requires an outcome and notes, and source event history remains immutable.

Live manager assignment and OPEN -> IN_PROGRESS -> CLOSED transitions are transactional. Each update appends a history record and increments a version token; stale writes are rejected. Each baseline dataset has its own namespace so regeneration cannot attach old case history to unrelated alerts.

## Evaluation and verification

The full benchmark contains 4,652 planted anomaly records; all were independently detected with zero false positives or false negatives for seed 20261022. Precision, recall and F1 are 1.0 on this controlled benchmark. Results include per-rule coverage and explicit benign damage/return false-positive analysis. All unplanted synthetic records are negatives by construction. These scores do not establish real-world accuracy.

The full dataset passes 85 recorded validation checks with zero unexpected errors. Declared malformed exceptions remain observable and are reported separately. Two full-scale regenerations produce identical row counts and checksums. See VERIFICATION.md and the machine-readable reports for evidence. Automated tests cover accounting corruption, independent detection, relationship failures, lifecycle rules, persistent updates, simultaneous saves, filters, and browser interactions.

## Scope and limitations

All records are synthetic and contain no real personal data. The manager selector is a demonstration identity, not authentication. Durable review storage is local SQLite; multi-user deployment needs identity integration and operational hosting/backup decisions. Roles and store/SKU masters are run snapshots rather than effective-dated HR or master-data histories. Generated returns are sellable; non-sellable loss is represented by damage movements. Exposure deduplicates the same event and transfer pair but distinct related events may overlap. Confirmed-loss financial reporting and automatic stock correction require domain review and additional workflows.

## Submission contents

The ZIP includes runnable source, dependencies, tests, a complete starter sample, field documentation, ER diagrams, SQL schema, provenance, full-run verification reports, actual dashboard screenshots and a demonstration script. Full-size CSVs and local workflow databases are excluded; the full dataset can be regenerated with the documented command.

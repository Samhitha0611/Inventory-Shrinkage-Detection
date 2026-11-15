# Data dictionary

CSV empty strings represent absent conditional/optional fields; convert optional foreign keys to SQL NULL on import. CSV booleans True/False map to SQL 1/0. Quantities are whole units; money is INR. Generated timestamps are fictional naive ISO-8601 values; live audit updates are stored as UTC ISO values without a suffix for compatibility.

Every field below documents the data contract. The validator checks structural/accounting rules and reports exact planted exceptions separately. Master snapshots do not model effective-dated role or store history; Promotion and Shift have explicit effective dates. Refer to [relationships](ER_DIAGRAM.md) and [business rules](BUSINESS_RULES.md).

## CycleCount

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| count_id | string | required | See validation rule | n/a | primary key | Existing CycleCount key; CNT-2026- plus six digits. |
| store_id | string | required | See validation rule | n/a | not unique | Store.store_id; Existing Store primary key; STORE- plus six digits. |
| sku_id | string | required | See validation rule | n/a | not unique | SKU.sku_id; Existing SKU primary key; SKU- plus six digits. |
| count_ts | ISO timestamp | required | See validation rule | n/a | not unique | Valid ISO-8601 timestamp. Expected stock includes only movements at or before this time. |
| expected_qty | integer | required | See validation rule | units | not unique | Integer >= 0; opening plus signed ledger at count_ts. |
| counted_qty | integer | required | See validation rule | units | not unique | Integer >= 0; observed physical quantity. |
| variance_qty | integer | required | See validation rule | units | not unique | Integer equal to counted_qty minus expected_qty. |
| employee_role_id | string | required | See validation rule | n/a | not unique | EmployeeRole.employee_role_id; Existing EmployeeRole primary key; ROLE- plus four digits. |
| reference_movement_id | string | required | See validation rule | n/a | not unique | InventoryMovement.movement_id; Required InventoryMovement FK; same store/SKU and timestamp <= count_ts, except declared order anomaly. |

## EmployeeRole

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| employee_role_id | string | required | See validation rule | n/a | primary key | Existing EmployeeRole primary key; ROLE- plus four digits. |
| employee_id | string | required | See validation rule | n/a | unique | Unique synthetic employee identifier; EMP- plus five digits. |
| role | string | required | STORE_OPERATOR, MANAGER, ANALYST, WAREHOUSE_OPERATOR | n/a | not unique | Permitted role enum; movement and count permissions follow BUSINESS_RULES.md. |

## ground_truth

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| record_id | string | required | See validation rule | n/a | not unique | InventoryMovement.movement_id or CycleCount.count_id; Existing movement_id or count_id in the evaluation population. |
| issue_type | string | required | See validation rule | n/a | not unique | Known planted anomaly family or explicit LEGITIMATE_DAMAGE / LEGITIMATE_RETURN. |
| expected_label | string | required | ANOMALY, BENIGN | n/a | not unique | ANOMALY or BENIGN; evaluation-only. |
| expected_decision | string | required | See validation rule | n/a | not unique | Documented expected rule decision; evaluation-only. |

## InventoryMovement

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| movement_id | string | required | See validation rule | n/a | primary key | Existing InventoryMovement key; MOV-2026- plus eight digits. |
| store_id | string | required | See validation rule | n/a | not unique | Store.store_id; Existing Store primary key; STORE- plus six digits. |
| sku_id | string | required | See validation rule | n/a | not unique | SKU.sku_id; Existing SKU primary key; SKU- plus six digits. |
| movement_type | string | required | SALE, RECEIPT, RETURN, DAMAGE, ADJUSTMENT, TRANSFER_IN, TRANSFER_OUT | n/a | not unique | Permitted movement enum; direction must agree with signed_qty except declared double-debit injections. |
| quantity | integer | required | See validation rule | units | not unique | Positive integer units; absolute signed_qty for movement rows. |
| signed_qty | integer | required | See validation rule | units | not unique | Nonzero signed integer; magnitude equals quantity. Stock at any time uses the signed ledger. |
| movement_ts | ISO timestamp | required | See validation rule | n/a | not unique | Valid ISO-8601 timestamp within the linked store shift. |
| reason | string | conditional (see rule) | See validation rule | n/a | not unique | Required for adjustment; damage, receipt, return and transfer have documented reasons; sale may be empty. |
| employee_role_id | string | required | See validation rule | n/a | not unique | EmployeeRole.employee_role_id; Existing EmployeeRole primary key; ROLE- plus four digits. |
| shift_id | string | required | See validation rule | n/a | not unique | Shift.shift_id; Existing Shift primary key; linked store must match movement store. |
| promotion_id | string | optional | See validation rule | n/a | not unique | Promotion.promotion_id; Existing Promotion key when provided; movement SKU/date must match its promotion. |
| transfer_id | string | conditional (see rule) | See validation rule | n/a | not unique | Required for transfer types; groups exactly two reciprocal rows; empty for non-transfers. |
| related_movement_id | string | conditional (see rule) | See validation rule | n/a | not unique | InventoryMovement.movement_id; Required for paired transfers; reciprocal InventoryMovement link; same SKU and different store. |

## Investigation

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| investigation_id | string | required | See validation rule | n/a | primary key | Existing Investigation key; INV-2026- plus six digits. |
| alert_id | string | required | See validation rule | n/a | not unique | ShrinkageAlert.alert_id; Existing ShrinkageAlert key; SHR-2026- plus six digits. |
| owner_employee_role_id | string | required | See validation rule | n/a | not unique | EmployeeRole.employee_role_id; Required EmployeeRole FK with MANAGER role. |
| status | string | required | OPEN, IN_PROGRESS, CLOSED | n/a | not unique | OPEN, IN_PROGRESS or CLOSED. CSV alert status is an initial snapshot; live dashboard derives status from its investigation. |
| outcome | string | conditional (see rule) | See validation rule | n/a | not unique | Required for CLOSED; empty while active. Live enum: CONFIRMED_LOSS, PROCESS_ERROR, LEGITIMATE_VARIANCE, INCONCLUSIVE. |
| opened_at | ISO timestamp | required | See validation rule | n/a | not unique | Valid ISO-8601 timestamp equal to the initial creation event. |
| closed_at | ISO timestamp | conditional (see rule) | See validation rule | n/a | not unique | Required for CLOSED, >= opened_at and equal to closing event time; otherwise empty. |

## InvestigationEvent

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| event_id | string | required | See validation rule | n/a | primary key | Unique immutable event identifier; generated CSV uses IEV- plus eight digits. |
| investigation_id | string | required | See validation rule | n/a | not unique | Investigation.investigation_id; Existing Investigation key; INV-2026- plus six digits. |
| from_status | string | conditional (see rule) | , OPEN, IN_PROGRESS | n/a | not unique | Empty only on creation; otherwise preceding state in the event history. |
| to_status | string | required | OPEN, IN_PROGRESS, CLOSED | n/a | not unique | OPEN, IN_PROGRESS or CLOSED; valid generated transitions are creation -> OPEN -> IN_PROGRESS -> CLOSED. |
| event_ts | ISO timestamp | required | See validation rule | n/a | not unique | Valid chronological ISO-8601 timestamp; final transition must agree with case snapshot. |
| outcome | string | conditional (see rule) | See validation rule | n/a | not unique | Required for CLOSED; empty while active. Live enum: CONFIRMED_LOSS, PROCESS_ERROR, LEGITIMATE_VARIANCE, INCONCLUSIVE. |

## Promotion

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| promotion_id | string | required | See validation rule | n/a | primary key | Existing Promotion key when provided; movement SKU/date must match its promotion. |
| sku_id | string | required | See validation rule | n/a | not unique | SKU.sku_id; Existing SKU primary key; SKU- plus six digits. |
| start_date | date | required | See validation rule | n/a | not unique | Valid YYYY-MM-DD date; not after end_date. |
| end_date | date | required | See validation rule | n/a | not unique | Valid YYYY-MM-DD date; not before start_date. |
| discount_pct | decimal | required | See validation rule | percent | not unique | Between 0 and 80 inclusive. |

## Return

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| return_id | string | required | See validation rule | n/a | primary key | Unique RET-2026- plus six digits. |
| store_id | string | required | See validation rule | n/a | not unique | Store.store_id; Existing Store primary key; STORE- plus six digits. |
| sku_id | string | required | See validation rule | n/a | not unique | SKU.sku_id; Existing SKU primary key; SKU- plus six digits. |
| original_sale_movement_id | string | required | See validation rule | n/a | not unique | InventoryMovement.movement_id; Required earlier SALE of the same store/SKU. Cumulative returns cannot exceed sale quantity. |
| movement_id | string | required | See validation rule | n/a | not unique | InventoryMovement.movement_id; Existing InventoryMovement key; MOV-2026- plus eight digits. |
| quantity | integer | required | See validation rule | units | not unique | Positive integer units; absolute signed_qty for movement rows. |
| condition | string | required | SELLABLE, DAMAGED | n/a | not unique | SELLABLE or DAMAGED. Current generator produces SELLABLE returns; damage uses separate DAMAGE movements. |
| return_ts | ISO timestamp | required | See validation rule | n/a | not unique | Valid ISO-8601 timestamp equal to linked RETURN movement timestamp. |

## Shift

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| shift_id | string | required | See validation rule | n/a | primary key | Existing Shift primary key; linked store must match movement store. |
| store_id | string | required | See validation rule | n/a | not unique | Store.store_id; Existing Store primary key; STORE- plus six digits. |
| shift_date | date | required | See validation rule | n/a | not unique | Valid YYYY-MM-DD date. |
| start_time | time | required | See validation rule | n/a | not unique | Valid HH:MM time; strictly earlier than end_time. |
| end_time | time | required | See validation rule | n/a | not unique | Valid HH:MM time; strictly after start_time. |
| shift_name | string | required | DAY | n/a | not unique | DAY in generated data. |

## ShrinkageAlert

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| alert_id | string | required | See validation rule | n/a | primary key | Existing ShrinkageAlert key; SHR-2026- plus six digits. |
| store_id | string | required | See validation rule | n/a | not unique | Store.store_id; Existing Store primary key; STORE- plus six digits. |
| sku_id | string | required | See validation rule | n/a | not unique | SKU.sku_id; Existing SKU primary key; SKU- plus six digits. |
| movement_id | string | exactly one of movement_id / count_id | See validation rule | n/a | not unique | InventoryMovement.movement_id; Existing InventoryMovement key; MOV-2026- plus eight digits. |
| count_id | string | exactly one of movement_id / count_id | See validation rule | n/a | not unique | CycleCount.count_id; Existing CycleCount key; CNT-2026- plus six digits. |
| reason_code | string | required | See validation rule | n/a | not unique | Evidence-based detector rule code. |
| severity | string | required | LOW, MEDIUM, HIGH | n/a | not unique | LOW, MEDIUM or HIGH; current detector emits MEDIUM or HIGH by exposure. |
| risk_score | decimal | required | See validation rule | dimensionless | not unique | Real in [0,1]; ordinal tiers, not calibrated probabilities. |
| status | string | required | OPEN, IN_PROGRESS, CLOSED | n/a | not unique | OPEN, IN_PROGRESS or CLOSED. CSV alert status is an initial snapshot; live dashboard derives status from its investigation. |
| created_at | ISO timestamp | required | See validation rule | n/a | not unique | Valid ISO-8601 source-event timestamp. |
| evidence | JSON object | required | See validation rule | n/a | not unique | Required valid JSON object containing source IDs, conflicting values or thresholds. |
| exposure_inr | decimal | required | See validation rule | INR | not unique | Nonnegative affected units multiplied by unit cost, rounded to two decimals; not confirmed loss. |

## SKU

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| sku_id | string | required | See validation rule | n/a | primary key | Existing SKU primary key; SKU- plus six digits. |
| sku_name | string | required | See validation rule | n/a | not unique | Nonempty synthetic product name. |
| category | string | required | GROCERY, HOME, APPAREL, ELECTRONICS | n/a | not unique | GROCERY, HOME, APPAREL or ELECTRONICS. |
| unit_cost_inr | decimal | required | See validation rule | INR | not unique | Nonnegative acquisition cost, rounded to two decimal places. |
| unit_price_inr | decimal | required | See validation rule | INR | not unique | Nonnegative selling price; generated above cost, rounded to two decimal places. |
| active | boolean | required | True, False | n/a | not unique | True or False; master records are active in generated snapshots. |

## Store

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| store_id | string | required | See validation rule | n/a | primary key | Existing Store primary key; STORE- plus six digits. |
| store_name | string | required | See validation rule | n/a | not unique | Nonempty synthetic store display name. |
| city | string | required | See validation rule | n/a | not unique | Nonempty city; synthetic geography aligned with region. |
| region | string | required | SOUTH, WEST, NORTH | n/a | not unique | SOUTH, WEST or NORTH in this generator. |
| store_type | string | required | RETAIL, WAREHOUSE | n/a | not unique | RETAIL or WAREHOUSE. |
| active | boolean | required | True, False | n/a | not unique | True or False; master records are active in generated snapshots. |

## StoreSKUOpeningBalance

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| store_id | string | required | See validation rule | n/a | part of composite PK | Store.store_id; Existing Store primary key; STORE- plus six digits. |
| sku_id | string | required | See validation rule | n/a | part of composite PK | SKU.sku_id; Existing SKU primary key; SKU- plus six digits. |
| opening_qty | integer | required | See validation rule | units | not unique | Integer >= 0; initial stock for this unique store/SKU pair. |

## LiveDataset

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| dataset_id | string | required | See validation rule | n/a | primary key | SHA-256 of alerts, initial investigations/events and roles; isolates each baseline dataset. |

## LiveCaseRecord

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| dataset_id | string | required | See validation rule | n/a | composite PK with dataset_id | LiveDataset.dataset_id; SHA-256 of alerts, initial investigations/events and roles; isolates each baseline dataset. |
| investigation_id | string | required | See validation rule | n/a | composite PK with dataset_id | source CSV identifier; Existing Investigation key; INV-2026- plus six digits. |
| alert_id | string | required | See validation rule | n/a | unique within dataset | source CSV identifier; Existing ShrinkageAlert key; SHR-2026- plus six digits. |
| owner_employee_role_id | string | required | See validation rule | n/a | not unique | EmployeeRole.employee_role_id; Required EmployeeRole FK with MANAGER role. |
| status | string | required | OPEN, IN_PROGRESS, CLOSED | n/a | not unique | OPEN, IN_PROGRESS or CLOSED. CSV alert status is an initial snapshot; live dashboard derives status from its investigation. |
| outcome | string | conditional (see rule) | See validation rule | n/a | not unique | Required for CLOSED; empty while active. Live enum: CONFIRMED_LOSS, PROCESS_ERROR, LEGITIMATE_VARIANCE, INCONCLUSIVE. |
| opened_at | ISO timestamp | required | See validation rule | n/a | not unique | Valid ISO-8601 timestamp equal to the initial creation event. |
| closed_at | ISO timestamp | conditional (see rule) | See validation rule | n/a | not unique | Required for CLOSED, >= opened_at and equal to closing event time; otherwise empty. |
| version | integer | required | See validation rule | n/a | not unique | Nonnegative integer; incremented once per committed live update; optimistic concurrency token. |

## LiveAuditEvent

| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |
|---|---|---|---|---|---|---|
| event_id | integer | required | See validation rule | n/a | primary key | SQLite AUTOINCREMENT integer; immutable and unique across dataset namespaces. |
| dataset_id | string | required | See validation rule | n/a | not unique | LiveDataset.dataset_id; SHA-256 of alerts, initial investigations/events and roles; isolates each baseline dataset. |
| investigation_id | string | required | See validation rule | n/a | not unique | LiveCaseRecord (dataset_id, investigation_id); Existing Investigation key; INV-2026- plus six digits. |
| action | string | required | CREATE, ASSIGN, TRANSITION | n/a | not unique | CREATE, ASSIGN or TRANSITION. ASSIGN preserves state while changing owner. |
| from_status | string | conditional (see rule) | , OPEN, IN_PROGRESS | n/a | not unique | Empty only on creation; otherwise preceding state in the event history. Live ASSIGN events preserve the status. |
| to_status | string | required | OPEN, IN_PROGRESS, CLOSED | n/a | not unique | OPEN, IN_PROGRESS or CLOSED; valid generated transitions are creation -> OPEN -> IN_PROGRESS -> CLOSED. Live ASSIGN events preserve the status. |
| event_ts | ISO timestamp | required | See validation rule | n/a | not unique | Valid chronological ISO-8601 timestamp; final transition must agree with case snapshot. |
| outcome | string | conditional (see rule) | See validation rule | n/a | not unique | Required for CLOSED; empty while active. Live enum: CONFIRMED_LOSS, PROCESS_ERROR, LEGITIMATE_VARIANCE, INCONCLUSIVE. |
| owner_employee_role_id | string | required | See validation rule | n/a | not unique | EmployeeRole.employee_role_id; Required EmployeeRole FK with MANAGER role. |
| actor_employee_role_id | string | required | See validation rule | n/a | not unique | EmployeeRole.employee_role_id; EmployeeRole FK with MANAGER role; demo acting identity, not authenticated login. |
| note | string | conditional (see rule) | See validation rule | n/a | not unique | Free text; nonempty investigation notes required when closing. |

Live tables use the same namespace-scoped case IDs as source CSVs. Source CSVs stay immutable during review. SQLite protects audit events against UPDATE/DELETE; the service serializes writes and checks a version token. Generated and live snapshots have separate validation scopes.

Ground truth is an evaluation-only sidecar and is never an operational feature or dashboard input.

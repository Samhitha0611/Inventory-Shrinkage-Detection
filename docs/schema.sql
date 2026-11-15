-- SQLite starter schema. Run with: sqlite3 inventory.db < docs/schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE Store (
  store_id TEXT PRIMARY KEY, store_name TEXT NOT NULL, city TEXT NOT NULL,
  region TEXT NOT NULL, store_type TEXT NOT NULL CHECK(store_type IN ('RETAIL','WAREHOUSE')),
  active INTEGER NOT NULL CHECK(active IN (0,1))
);
CREATE TABLE SKU (
  sku_id TEXT PRIMARY KEY, sku_name TEXT NOT NULL, category TEXT NOT NULL,
  unit_cost_inr REAL NOT NULL CHECK(unit_cost_inr >= 0),
  unit_price_inr REAL NOT NULL CHECK(unit_price_inr >= 0), active INTEGER NOT NULL
);
CREATE TABLE EmployeeRole (
  employee_role_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL UNIQUE, role TEXT NOT NULL
);
CREATE TABLE Shift (
  shift_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  shift_date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, shift_name TEXT NOT NULL
);
CREATE TABLE Promotion (
  promotion_id TEXT PRIMARY KEY, sku_id TEXT NOT NULL REFERENCES SKU(sku_id),
  start_date TEXT NOT NULL, end_date TEXT NOT NULL, discount_pct REAL NOT NULL
    CHECK(discount_pct BETWEEN 0 AND 80), CHECK(end_date >= start_date)
);
CREATE TABLE StoreSKUOpeningBalance (
  store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id), opening_qty INTEGER NOT NULL CHECK(opening_qty >= 0),
  PRIMARY KEY(store_id, sku_id)
);
CREATE TABLE InventoryMovement (
  movement_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id), movement_type TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity > 0), signed_qty INTEGER NOT NULL,
  movement_ts TEXT NOT NULL, reason TEXT, employee_role_id TEXT REFERENCES EmployeeRole(employee_role_id),
  shift_id TEXT REFERENCES Shift(shift_id), promotion_id TEXT REFERENCES Promotion(promotion_id),
  transfer_id TEXT, related_movement_id TEXT REFERENCES InventoryMovement(movement_id)
);
CREATE TABLE CycleCount (
  count_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id), count_ts TEXT NOT NULL,
  expected_qty INTEGER NOT NULL, counted_qty INTEGER NOT NULL, variance_qty INTEGER NOT NULL,
  employee_role_id TEXT REFERENCES EmployeeRole(employee_role_id),
  reference_movement_id TEXT NOT NULL REFERENCES InventoryMovement(movement_id)
);
CREATE TABLE "Return" (
  return_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id),
  original_sale_movement_id TEXT REFERENCES InventoryMovement(movement_id),
  movement_id TEXT REFERENCES InventoryMovement(movement_id), quantity INTEGER NOT NULL,
  condition TEXT NOT NULL CHECK(condition IN ('SELLABLE','DAMAGED')), return_ts TEXT NOT NULL
);
CREATE TABLE ShrinkageAlert (
  alert_id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES Store(store_id),
  sku_id TEXT NOT NULL REFERENCES SKU(sku_id),
  movement_id TEXT REFERENCES InventoryMovement(movement_id), count_id TEXT REFERENCES CycleCount(count_id),
  reason_code TEXT NOT NULL, severity TEXT NOT NULL, risk_score REAL NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL, evidence TEXT NOT NULL, exposure_inr REAL NOT NULL
);
CREATE TABLE Investigation (
  investigation_id TEXT PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES ShrinkageAlert(alert_id),
  owner_employee_role_id TEXT REFERENCES EmployeeRole(employee_role_id),
  status TEXT NOT NULL CHECK(status IN ('OPEN','IN_PROGRESS','CLOSED')), outcome TEXT,
  opened_at TEXT NOT NULL, closed_at TEXT
);
-- Evaluation labels intentionally live outside the operational schema.

CREATE TABLE InvestigationEvent (
  event_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES Investigation(investigation_id),
  from_status TEXT NOT NULL, to_status TEXT NOT NULL, event_ts TEXT NOT NULL, outcome TEXT NOT NULL,
  CHECK ((from_status='' AND to_status='OPEN') OR (from_status='OPEN' AND to_status='IN_PROGRESS') OR (from_status='IN_PROGRESS' AND to_status='CLOSED'))
);

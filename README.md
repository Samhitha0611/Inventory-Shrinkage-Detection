# Inventory Shrinkage Detection

A reproducible synthetic inventory monitoring project. Operational evidence is generated first, independent rules produce explainable alerts, and a separate evaluation step compares predictions with planted ground truth. Alerts are investigation leads, not proof of theft.

## Run the complete workflow

Python 3.10+; the pipeline uses the standard library. Pandas and Streamlit are used only by the dashboard.

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py src/generate_data.py --profile full
py src/validate_data.py
py src/evaluate.py
py src/check_reproducibility.py --profile full
streamlit run app.py
```

Use `--profile starter` for 10 stores, 100 SKUs, 10,000 movements and 500 counts. Full scale produces 100 stores, 5,000 SKUs, 1,000,000 movements and 20,000 counts. Both use seed `20261022`; `--seed` changes it. Generator, validator, detector and evaluator accept `--out PATH`.

Generation replaces the dataset at the selected output path and invokes independent detection. To rerun detection on existing operational data:

```powershell
py src/detect_anomalies.py
py src/evaluate.py
```

If the operational data or detected alerts change, regenerate downstream investigation snapshots before validation. Synthetic investigations are initialized by the generator, with append-only creation events. Validation also supports subsequent OPEN -> IN_PROGRESS -> CLOSED event histories.

## Evidence and accounting

- Opening balances plus signed movements form the ledger. Replenishments are explicit receipts; stock is never silently clamped.
- Counts reconcile to movements at or before each count timestamp, including the deliberate ordering exception.
- Movements fall within generated shifts. Roles have explicit permitted movement types.
- Transfers have reciprocal links and opposite signed quantities. Planted failures deliberately debit the destination too, making stock disappear at both ends. These are retained as evidence and flagged, not silently repaired.
- Wrong-store exceptions retain valid foreign keys but contradict the linked shift's store.
- Missing reasons, three negative adjustments within sixty seconds, and count shortages of at least five units have independent detection rules.
- Each return references an earlier sale of the same store/SKU; cumulative returned units cannot exceed that sale. Damage and sellable returns provide benign examples.
- Alert evidence records the actual conflicting fields or movement IDs. Exposure is quantity times SKU cost; severity/risk tiers are deterministic exposure bands, not calibrated probabilities.

## Validation and evaluation

`validation_summary.json` includes all checks, unexpected errors, observed planted exceptions, and row counts. PASS means zero unexpected violations and that every expected structural exception is observable. Exact record/rule matching prevents an unrelated failure from being excused as a planted anomaly. Checks include primary/composite keys, foreign keys, enums, signs, stock running balances, as-of count reconciliation, transfers, dates, role authorization, return links, and investigation transitions/history.

`evaluation_report.json` contains overall and per-issue precision, recall, F1, false positives, false negatives, and explicit benign-damage/return results. The evaluation population is every movement and count. Unplanted synthetic records are treated as negative examples; predictions are deduplicated by record for overall scores. These metrics measure the synthetic benchmark only.

`ground_truth.csv` is read only by evaluation and exception accounting in validation. Neither the detector nor operational tables contain `issue_type`, `expected_label`, or other planted-label columns. The detector works even if the truth file is removed. The dashboard loads aggregate evaluation results, not row-level truth.

`manifest.json` records row counts and SHA-256 checksums for every generated CSV. The reproducibility checker generates twice in isolated temporary directories, compares manifests, and saves `reproducibility_check.json` without overwriting the active dataset. Temporary datasets are cleaned up automatically.

## Tests

```powershell
py -m unittest test_pipeline test_workflow test_app -v
```

Regression tests cover independent detection without truth, new unlabelled anomalies, stock/count corruption, negative stock, invalid FKs, duplicate keys, transfer failures, shift timing, role authorization, enum validation and valid/invalid investigation histories.

## Files

- `src/generate_data.py`: scalable generator
- `src/detect_anomalies.py`: independent evidence-based rules
- `src/validate_data.py`, `src/database.py`: indexed SQLite scratch validation
- `src/evaluate.py`: synthetic benchmark metrics
- `src/check_reproducibility.py`: isolated two-run checksum comparison
- `docs/`: schema, data dictionary, rules and provenance
- `app.py`: dashboard and evaluation summary

All records are synthetic. No external datasets or personal data are used. A production rollout would require access controls, hosted storage and backups, operational review and evaluation on representative real data.

## Review investigations

Filter alerts by store, SKU, severity, reason, investigation status and date. Select an alert to inspect its JSON evidence and optionally load linked inventory rows. Assign a manager, then advance OPEN -> IN_PROGRESS -> CLOSED. Closing requires a resolution and investigation notes. Closed cases are read-only; owner changes and transitions preserve audit history.

Live changes are stored transactionally in `data/workflow.sqlite3`. They do not modify generated CSVs, validation reports or checksum manifests. A fingerprint of the baseline alerts, investigations, events and roles selects an isolated dataset namespace. Identical regeneration resumes that namespace; changed data starts a new namespace and retains old history. Stale simultaneous updates are rejected. Back up the SQLite file to preserve review history. The acting-manager selector is a demo identity, not authentication.

The exposure metric groups duplicate alerts for the same source event and both sides of a transfer; it is review exposure, not confirmed financial loss. Downloads contain every matching alert, even when the on-screen table shows the first 250 rows.

## Documentation and submission

- [Complete field dictionary](docs/DATA_DICTIONARY.md), also available as [JSON](docs/data_dictionary.json)
- [ER diagrams and lifecycle](docs/ER_DIAGRAM.md)
- [Project report](docs/PROJECT_REPORT.md)
- [Five-minute demonstration and actual screenshots](docs/DEMO.md)
- [Verification results](docs/VERIFICATION.md)
- [Runnable starter sample](examples/README.md)

```powershell
py -m unittest test_pipeline test_workflow test_app -v
py scripts/prepare_submission.py
```

The shareable archive is `artifacts/inventory_shrinkage_submission.zip`. It includes source, documentation, screenshots, tests, the complete starter sample and full-run verification reports. It excludes the virtual environment, live investigation databases and full-size CSVs. `--skip-sample` repackages an already validated sample. Optional real-browser checks and screenshot capture use `requirements-dev.txt` and `py scripts/capture_demo.py` with installed Microsoft Edge.

To refresh the field dictionary after schema changes, run `py scripts/build_documentation.py`. For isolated tests or alternate datasets, set `INVENTORY_DATA_DIR` and optionally `INVENTORY_WORKFLOW_DB` before launching Streamlit.

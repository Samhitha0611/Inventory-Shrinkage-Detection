# Runnable sample dataset

`sample/` contains a complete, linked starter dataset: 10 stores, 100 SKUs, 10,000 movements and 500 counts. It uses the same generator and seed 20261022 as the full dataset. Ground truth is supplied only for evaluation. Validation, evaluation, reproducibility and checksum reports are included.

Run the sample dashboard from the project root:

```powershell
$env:INVENTORY_DATA_DIR = (Resolve-Path examples/sample).Path
.venv\Scripts\streamlit.exe run app.py
```

The default local review database is `examples/workflow.sqlite3`; it is created on first use and is excluded from the submission package. Regenerating identical data resumes existing case history. Changed baseline data selects a new namespace, preserving the previous one.

Verify the sample:

```powershell
py src/validate_data.py --out examples/sample
py src/evaluate.py --out examples/sample
```

To return to the full dataset, start a new terminal or remove the dataset override before launching the app:

```powershell
Remove-Item Env:INVENTORY_DATA_DIR
```

Rebuild this sample and the source/documentation package with `py scripts/prepare_submission.py`. Full-size CSVs, environment folders and live investigation history are intentionally absent from the ZIP; `verification/full/` contains the full-run reports. Generate full data locally with `py src/generate_data.py --profile full`.

# Agent Guide

Use `skills/greenampt-nash-muskingum/SKILL.md` first for this repository.

## Operating Rules

- Treat this project as a teaching/research rainfall-runoff prototype, not an operational flood-forecasting system.
- Do not describe synthetic example-data metrics as real watershed validation.
- Keep `calibrate.py` as the calibration CLI, `forecast.py` as the forecast CLI, and `generate_example_data.py` as the synthetic demo-data generator.
- Keep generated files out of Git unless the user explicitly asks to publish an example output artifact.
- Preserve train/test separation when modifying calibration workflows.
- Reject or penalize unstable Muskingum parameters instead of silently changing `K_musk` or `x_musk`.

## Standard Commands

Install:

```bash
python -m pip install -e .
```

Generate example data:

```bash
python generate_example_data.py
```

Calibrate:

```bash
python calibrate.py dataset/example_data.csv -o params/calibrated_params.json --figures-dir outputs -a 150 --dt 1 -e 100 -p 80 --seed 42
```

Forecast:

```bash
python forecast.py dataset/example_forecast.csv -p params/calibrated_params.json -o outputs/forecast_result.csv --plot outputs/forecast_result.png
```

Verify:

```bash
python -m compileall .
python -m unittest discover -s tests
python skills/greenampt-nash-muskingum/scripts/smoke_check.py --epochs 2 --population 6
```

## Release Hygiene

Before publishing to GitHub, inspect the staged set and confirm it excludes:

- `__pycache__/`
- `outputs/`
- `params/`
- private Excel workbooks
- real project data that lacks explicit permission for public release

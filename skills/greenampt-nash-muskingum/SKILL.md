---
name: greenampt-nash-muskingum
description: "Use this skill when working with the GreenAmpt-Nash-Muskingum rainfall-runoff research prototype: installing the repository, generating synthetic example data, calibrating Green-Ampt/Nash/Muskingum parameters, running forecasts, validating outputs, packaging for GitHub, or explaining model limits to humans or other agents."
---

# GreenAmpt-Nash-Muskingum

Use this repository as a teaching and research prototype for lumped rainfall-runoff modeling. Do not present synthetic example-data results as professional validation.

## Quick Workflow

From the repository root:

```bash
python -m pip install -e .
python generate_example_data.py
python calibrate.py dataset/example_data.csv -o params/calibrated_params.json --figures-dir outputs -a 150 --dt 1 -e 100 -p 80 --seed 42
python forecast.py dataset/example_forecast.csv -p params/calibrated_params.json -o outputs/forecast_result.csv --plot outputs/forecast_result.png
```

For a fast agent smoke check:

```bash
python skills/greenampt-nash-muskingum/scripts/smoke_check.py --epochs 2 --population 6
```

## Use Real Data

Calibration CSV must include `Rainfall_mmh` and `Observed_Flow_m3s`; `Time_h` and `Split` are optional. Prefer explicit `Split=train/test` labels. Without labels, `calibrate.py` uses chronological `--train-ratio`.

Forecast CSV must include `Forecast_Rainfall_mmh` or `Rainfall_mmh`.

Read `references/io-schema.md` when creating or checking input files.

## Validate Before Claims

Run at least:

```bash
python -m compileall .
python -m unittest discover -s tests
python skills/greenampt-nash-muskingum/scripts/smoke_check.py --epochs 2 --population 6
```

Report what data was used. If only the synthetic example data was used, say the result is a workflow smoke test, not real-basin validation.

## Professional Boundaries

Read `references/model-card.md` before writing public descriptions, marketplace copy, papers, or repository summaries.

Required wording:

- Acceptable: "teaching/research prototype", "secondary development template", "synthetic example workflow".
- Avoid: "operational flood forecasting system", "engineering validated", "safety-critical decision system".
- Never use this repository alone for evacuation, dam operation, or regulatory decisions.

## Release Hygiene

Before staging or publishing:

```bash
git status --short --ignored
```

Do not publish caches, `outputs/`, local `params/`, private Excel files, real project data, or credentials. Keep `dataset/example_data.csv` and `dataset/example_forecast.csv` only as synthetic demonstration data.

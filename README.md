# GreenAmpt-Nash-Muskingum

A Python research prototype for lumped rainfall-runoff simulation and flood routing:

```text
rainfall -> Green-Ampt excess rainfall -> Nash unit hydrograph -> Muskingum routing -> discharge
```

This repository is intended for teaching, research prototyping, and secondary development. It is not a professionally validated operational flood forecasting system.

## What Is Included

- Green-Ampt infiltration/excess-rainfall calculation.
- Nash unit hydrograph runoff concentration.
- Muskingum channel routing with explicit stability checks.
- WOA-based parameter calibration using `mealpy`.
- Chronological or explicit train/test split.
- NSE, RMSE, MAE, PBIAS, correlation, and peak-error metrics.
- Diagnostic figures and JSON outputs.
- A platform-neutral agent skill in `skills/greenampt-nash-muskingum/SKILL.md`.

## Installation

Clone the repository and install the package:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

For script-only use without installing the package:

```bash
python -m pip install -r requirements.txt
```

Python 3.11 or newer is recommended.

## Quick Start

Generate synthetic demonstration data:

```bash
python generate_example_data.py
```

Calibrate parameters on the training period and evaluate the test period:

```bash
python calibrate.py dataset/example_data.csv -o params/calibrated_params.json --figures-dir outputs -a 150 --dt 1 -e 100 -p 80 --seed 42
```

Run a forecast from a rainfall CSV:

```bash
python forecast.py dataset/example_forecast.csv -p params/calibrated_params.json -o outputs/forecast_result.csv --plot outputs/forecast_result.png
```

Installed console commands are also available:

```bash
gnm-generate-example
gnm-calibrate dataset/example_data.csv
gnm-forecast dataset/example_forecast.csv
```

## Input Data

Calibration CSV columns:

| Column | Unit | Required | Meaning |
|---|---:|---:|---|
| `Time_h` | h | no | Time from the start of the event. Row index is used if omitted. |
| `Rainfall_mmh` | mm/h | yes | Rainfall intensity per time step. |
| `Observed_Flow_m3s` | m3/s | yes | Observed discharge. |
| `Split` | - | no | Use `train` or `test` labels. If omitted, chronological `--train-ratio` is used. |

Forecast CSV columns:

| Column | Unit | Required | Meaning |
|---|---:|---:|---|
| `Forecast_Rainfall_mmh` | mm/h | yes | Forecast rainfall intensity. |
| `Rainfall_mmh` | mm/h | alternative | Accepted when `Forecast_Rainfall_mmh` is absent. |

Rainfall intensity is converted internally from mm/h to m/s. Total rainfall depth is computed as `sum(intensity_mmh) * dt_h`, so non-1-hour time steps are supported.

## Parameters

| Submodel | Parameter | Unit | Default search range |
|---|---|---:|---|
| Green-Ampt | `Ks` | m/s | `1e-8` to `1e-5` |
| Green-Ampt | `suction_head` | m | `0.005` to `0.5` |
| Green-Ampt | `delta_theta` | - | `0.1` to `0.5` |
| Nash | `n` | - | `2.0` to `5.0` |
| Nash | `k` | h | `1.0` to `3.5` |
| Muskingum | `K_musk` | h | `0.5` to `10.0` |
| Muskingum | `x_musk` | - | `0.0` to `0.5` |

The Muskingum coefficients are only accepted when `2*K*x <= dt <= 2*K*(1-x)`. Invalid combinations are rejected during direct simulation and penalized during calibration.

## Validation Boundary

The included `dataset/example_data.csv` is synthetic data generated from the model plus noise. It is useful for smoke tests, reproducibility checks, workflow demonstrations, and teaching. It is not evidence of real-basin predictive skill.

Before using this project for a real watershed:

- Replace the synthetic data with traceable observed rainfall and discharge.
- Set parameter bounds from soil, watershed, and channel evidence.
- Keep train/test or calibration/validation periods separate.
- Report validation metrics and limitations honestly.
- Do not use this repository alone for safety-critical evacuation, dam operation, or regulatory decisions.

## Agent Skill

Agents should start with:

```text
AGENTS.md
skills/greenampt-nash-muskingum/SKILL.md
```

The skill gives fixed commands for setup, calibration, forecasting, smoke checks, and result interpretation. It is plain Markdown and can be used by any agent or by humans.

## Tests

Run:

```bash
python -m compileall .
python -m unittest discover -s tests
python skills/greenampt-nash-muskingum/scripts/smoke_check.py --epochs 2 --population 6
```

The smoke check uses synthetic demonstration data only.

## References

- Green, W.H. and Ampt, G.A. (1911). Studies on soil physics: I. The flow of air and water through soils. Journal of Agricultural Science.
- Nash, J.E. (1957). The form of the instantaneous unit hydrograph. IAHS Publication.
- McCarthy, G.T. (1938). The unit hydrograph and flood routing. US Army Corps of Engineers.
- Mirjalili, S. and Lewis, A. (2016). The Whale Optimization Algorithm. Advances in Engineering Software.

## License

MIT License. See `LICENSE`.

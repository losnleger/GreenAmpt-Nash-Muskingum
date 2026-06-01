# Input and Output Schema

## Calibration CSV

Required columns:

| Column | Unit | Meaning |
|---|---:|---|
| `Rainfall_mmh` | mm/h | Rainfall intensity for each time step. |
| `Observed_Flow_m3s` | m3/s | Observed discharge for each time step. |

Optional columns:

| Column | Unit | Meaning |
|---|---:|---|
| `Time_h` | h | Time from event start. If absent, row index is used. |
| `Split` | - | `train` or `test`. If absent, chronological `--train-ratio` is used. |

## Forecast CSV

Use one rainfall column:

| Column | Unit | Meaning |
|---|---:|---|
| `Forecast_Rainfall_mmh` | mm/h | Preferred forecast rainfall intensity column. |
| `Rainfall_mmh` | mm/h | Accepted fallback column. |

## Parameter JSON

`calibrate.py` writes:

- `model`
- `area_km2`
- `dt_h`
- `parameters`
- `performance.train`
- `performance.test`
- `calibration_config`
- `calibration_history`
- `series.train`
- `series.test`

## Output Files

Default calibration outputs:

- `params/calibrated_params.json`
- `outputs/train_result.png`
- `outputs/calibration_training_curve.png`
- `outputs/train_test_fit.png`

Default forecast outputs:

- `outputs/forecast_result.csv`
- `outputs/forecast_result.png`

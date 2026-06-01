# -*- coding: UTF-8 -*-
"""Generate example calibration and forecast rainfall data."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from core.model import GreenAmpt, MuskingumRouting, NashHydrographCalculator

TRUE_PARAMS = {
    "Ks": 4.0e-7,
    "suction_head": 0.18,
    "delta_theta": 0.25,
    "n": 3.0,
    "k": 2.3,
    "K_musk": 4.0,
    "x_musk": 0.08,
}
AREA_KM2 = 150.0
DT_H = 1.0
TOTAL_HOURS = 120
TRAIN_HOURS = 72
TEST_HOURS = 48


def _build_rainfall(total_hours: int = TOTAL_HOURS) -> np.ndarray:
    rain = np.zeros(total_hours)
    for i in range(total_hours):
        p1a = 22.0 * np.exp(-0.5 * ((i - 20) / 4.5) ** 2)
        p1b = 12.0 * np.exp(-0.5 * ((i - 48) / 5.0) ** 2)
        storm1 = p1a + p1b if i < 65 else 0.0

        p2a = 18.0 * np.exp(-0.5 * ((i - 90) / 4.0) ** 2)
        p2b = 8.0 * np.exp(-0.5 * ((i - 105) / 5.5) ** 2)
        storm2 = p2a + p2b if i >= 60 else 0.0

        transition = 2.0 * np.exp(-0.5 * ((i - 65) / 6.0) ** 2) if 60 <= i < 78 else 0.0
        rain[i] = max(storm1 + storm2 + transition, 0.0)
    return rain


def generate_example_data(
    output_dir: str | os.PathLike = Path("dataset"),
    seed: int = 42,
    verbose: bool = True,
) -> dict[str, Path]:
    """Write example train/test calibration data and a default forecast rainfall file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.RandomState(seed)
    rain = _build_rainfall()

    ga = GreenAmpt(
        TRUE_PARAMS["Ks"],
        TRUE_PARAMS["suction_head"],
        TRUE_PARAMS["delta_theta"],
        delta_t=DT_H * 3600.0,
    )
    rain_mps = rain / 1000.0 / 3600.0
    net_rain = np.array([ga.calculate_runoff(r) for r in rain_mps], dtype=float)
    nash = NashHydrographCalculator(n=TRUE_PARAMS["n"], k=TRUE_PARAMS["k"], area_km2=AREA_KM2, dt=DT_H)
    muskingum = MuskingumRouting(K=TRUE_PARAMS["K_musk"], x=TRUE_PARAMS["x_musk"], dt=DT_H)
    true_flow_full = muskingum.route_flow(nash.convolve_hydrograph(net_rain))
    obs_flow_clean = true_flow_full[:TOTAL_HOURS].copy()

    noise = rng.normal(0.0, 0.06 * obs_flow_clean.max(), size=TOTAL_HOURS)
    obs_flow = np.maximum(obs_flow_clean + noise, 0.0)
    split_label = np.array(["train"] * TRAIN_HOURS + ["test"] * TEST_HOURS)

    calibration_df = pd.DataFrame(
        {
            "Time_h": np.arange(TOTAL_HOURS, dtype=float),
            "Rainfall_mmh": np.round(rain, 2),
            "Observed_Flow_m3s": np.round(obs_flow, 2),
            "Split": split_label,
        }
    )
    calibration_csv = output_dir / "example_data.csv"
    calibration_df.to_csv(calibration_csv, index=False, encoding="utf-8-sig")

    forecast_df = pd.DataFrame(
        {
            "Time_h": np.arange(TEST_HOURS, dtype=float),
            "Forecast_Rainfall_mmh": np.round(rain[TRAIN_HOURS:], 2),
        }
    )
    forecast_csv = output_dir / "example_forecast.csv"
    forecast_df.to_csv(forecast_csv, index=False, encoding="utf-8-sig")

    if verbose:
        _print_report(calibration_csv, forecast_csv, rain, obs_flow)

    return {"calibration_csv": calibration_csv, "forecast_csv": forecast_csv}


def _print_report(calibration_csv: Path, forecast_csv: Path, rain: np.ndarray, obs_flow: np.ndarray) -> None:
    train_peak = float(obs_flow[:TRAIN_HOURS].max())
    train_peak_t = int(np.argmax(obs_flow[:TRAIN_HOURS]))
    train_rain_peak_t = int(np.argmax(rain[:TRAIN_HOURS]))
    test_peak = float(obs_flow[TRAIN_HOURS:].max())
    test_peak_t = int(np.argmax(obs_flow[TRAIN_HOURS:]) + TRAIN_HOURS)
    test_rain_peak_t = int(np.argmax(rain[TRAIN_HOURS:]) + TRAIN_HOURS)

    print(f"数据已生成: {calibration_csv}")
    print(f"预报降雨已生成: {forecast_csv}")
    print(f"  总历时: {TOTAL_HOURS}h")
    print(f"  训练集: 0-{TRAIN_HOURS - 1}h, 累计雨量: {rain[:TRAIN_HOURS].sum():.0f}mm")
    print(
        f"    雨峰 @ {train_rain_peak_t}h, 洪峰 {train_peak:.0f} m3/s @ {train_peak_t}h "
        f"(滞后 {train_peak_t - train_rain_peak_t}h)"
    )
    print(f"  测试集: {TRAIN_HOURS}-{TOTAL_HOURS - 1}h, 累计雨量: {rain[TRAIN_HOURS:].sum():.0f}mm")
    print(
        f"    雨峰 @ {test_rain_peak_t}h, 洪峰 {test_peak:.0f} m3/s @ {test_peak_t}h "
        f"(滞后 {test_peak_t - test_rain_peak_t}h)"
    )
    print("\n完成。运行: python calibrate.py  (率定) 或 python train.py  (一键演示)")


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    generate_example_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

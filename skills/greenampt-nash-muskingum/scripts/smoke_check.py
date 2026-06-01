#!/usr/bin/env python
"""Run a fast end-to-end smoke check without writing into the repository."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def run(cmd: list[str], env: dict[str, str]) -> None:
    print("+ " + " ".join(str(part) for part in cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a quick GreenAmpt-Nash-Muskingum workflow smoke check.")
    parser.add_argument("--epochs", type=int, default=2, help="WOA epochs for the quick calibration run.")
    parser.add_argument("--population", type=int, default=6, help="WOA population size for the quick calibration run.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the temporary smoke-check directory.")
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    temp_dir = Path(tempfile.mkdtemp(prefix="gnm_smoke_"))

    dataset_dir = temp_dir / "dataset"
    params_json = temp_dir / "params" / "calibrated_params.json"
    outputs_dir = temp_dir / "outputs"
    forecast_csv = outputs_dir / "forecast_result.csv"
    forecast_png = outputs_dir / "forecast_result.png"

    run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "from generate_example_data import generate_example_data; "
                f"generate_example_data(output_dir=Path(r'{dataset_dir}'), verbose=False)"
            ),
        ],
        env,
    )
    run(
        [
            sys.executable,
            "calibrate.py",
            str(dataset_dir / "example_data.csv"),
            "-o",
            str(params_json),
            "--figures-dir",
            str(outputs_dir),
            "-e",
            str(args.epochs),
            "-p",
            str(args.population),
            "--seed",
            "42",
            "--no-plots",
        ],
        env,
    )
    run(
        [
            sys.executable,
            "forecast.py",
            str(dataset_dir / "example_forecast.csv"),
            "-p",
            str(params_json),
            "-o",
            str(forecast_csv),
            "--plot",
            str(forecast_png),
        ],
        env,
    )

    required = [
        dataset_dir / "example_data.csv",
        dataset_dir / "example_forecast.csv",
        params_json,
        forecast_csv,
        forecast_png,
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Smoke check missing outputs: " + ", ".join(str(path) for path in missing))

    payload = json.loads(params_json.read_text(encoding="utf-8"))
    for key in ("parameters", "performance", "calibration_config"):
        if key not in payload:
            raise KeyError(f"Parameter JSON missing {key}")

    print(f"Smoke check passed in {temp_dir}")
    if not args.keep_temp:
        shutil.rmtree(temp_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from core.calibration_workflow import (
    DEFAULT_PARAMETER_BOUNDS,
    CalibrationResult,
    evaluate_simulation,
    _parameters_are_valid,
    split_calibration_data,
    write_calibration_outputs,
)
from core.model import MuskingumRouting, is_muskingum_stable


class CalibrationWorkflowTests(unittest.TestCase):
    def test_split_uses_explicit_train_test_labels(self):
        df = pd.DataFrame(
            {
                "Time_h": [0, 1, 2, 3],
                "Rainfall_mmh": [1.0, 2.0, 3.0, 4.0],
                "Observed_Flow_m3s": [10.0, 20.0, 30.0, 40.0],
                "Split": ["train", "test", "train", "test"],
            }
        )

        train, test = split_calibration_data(df, train_ratio=0.5)

        self.assertEqual(train["Time_h"].tolist(), [0, 2])
        self.assertEqual(test["Time_h"].tolist(), [1, 3])

    def test_split_without_labels_uses_ratio(self):
        df = pd.DataFrame(
            {
                "Time_h": list(range(10)),
                "Rainfall_mmh": np.ones(10),
                "Observed_Flow_m3s": np.arange(10, dtype=float),
            }
        )

        train, test = split_calibration_data(df, train_ratio=0.7)

        self.assertEqual(len(train), 7)
        self.assertEqual(len(test), 3)
        self.assertEqual(train["Split"].unique().tolist(), ["train"])
        self.assertEqual(test["Split"].unique().tolist(), ["test"])

    def test_evaluate_simulation_reports_fit_metrics(self):
        obs = np.array([1.0, 2.0, 3.0, 4.0])
        sim = np.array([1.0, 2.0, 2.0, 4.0])

        metrics = evaluate_simulation(obs, sim)

        self.assertAlmostEqual(metrics["NSE"], 0.8)
        self.assertAlmostEqual(metrics["RMSE_m3s"], 0.5)
        self.assertAlmostEqual(metrics["PBIAS_pct"], 10.0)
        self.assertEqual(metrics["hours"], 4)

    def test_muskingum_rejects_unstable_parameters_without_silent_rewrite(self):
        self.assertFalse(is_muskingum_stable(K=10.0, x=0.5, dt=1.0))
        self.assertFalse(_parameters_are_valid([1e-6, 0.1, 0.2, 3.0, 2.0, 10.0, 0.5], dt=1.0))

        with self.assertRaises(ValueError):
            MuskingumRouting(K=10.0, x=0.5, dt=1.0)

    def test_muskingum_keeps_valid_parameters_unchanged(self):
        routing = MuskingumRouting(K=4.0, x=0.08, dt=1.0)

        self.assertAlmostEqual(routing.K, 4.0)
        self.assertAlmostEqual(routing.x, 0.08)

    def test_write_outputs_includes_history_and_fit_figures(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "outputs"
            params_json = Path(tmp) / "params" / "calibrated_params.json"
            train_df = pd.DataFrame(
                {
                    "Time_h": [0, 1, 2],
                    "Rainfall_mmh": [0.0, 5.0, 0.0],
                    "Observed_Flow_m3s": [0.0, 2.0, 1.0],
                    "Split": ["train", "train", "train"],
                }
            )
            test_df = pd.DataFrame(
                {
                    "Time_h": [3, 4],
                    "Rainfall_mmh": [3.0, 0.0],
                    "Observed_Flow_m3s": [1.5, 0.8],
                    "Split": ["test", "test"],
                }
            )
            result = CalibrationResult(
                model="GreenAmpt-Nash-Muskingum",
                area_km2=150.0,
                dt_h=1.0,
                parameters={name: float(i + 1) for i, name in enumerate(DEFAULT_PARAMETER_BOUNDS)},
                performance={
                    "train": evaluate_simulation(
                        train_df["Observed_Flow_m3s"].to_numpy(),
                        np.array([0.0, 1.8, 1.2]),
                    ),
                    "test": evaluate_simulation(
                        test_df["Observed_Flow_m3s"].to_numpy(),
                        np.array([1.4, 0.9]),
                    ),
                },
                calibration_config={"epochs": 2, "pop_size": 3, "objective": "1 - NSE"},
                history={"epoch": [1, 2], "best_fitness": [0.7, 0.4], "best_nse": [0.3, 0.6]},
                series={
                    "train": {"observed": [0.0, 2.0, 1.0], "simulated": [0.0, 1.8, 1.2]},
                    "test": {"observed": [1.5, 0.8], "simulated": [1.4, 0.9]},
                },
            )

            written = write_calibration_outputs(
                result=result,
                train_df=train_df,
                test_df=test_df,
                output_json=params_json,
                figures_dir=out_dir,
                save_figures=True,
            )

            self.assertTrue(params_json.exists())
            self.assertTrue(written["summary_figure"].exists())
            self.assertTrue(written["training_figure"].exists())
            self.assertTrue(written["fit_figure"].exists())

            payload = json.loads(params_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["calibration_history"]["best_nse"], [0.3, 0.6])
            self.assertIn("series", payload)


if __name__ == "__main__":
    unittest.main()

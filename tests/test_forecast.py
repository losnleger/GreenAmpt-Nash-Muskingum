import tempfile
import unittest
from pathlib import Path

import pandas as pd

from forecast import run_forecast


class ForecastTests(unittest.TestCase):
    def test_total_rainfall_uses_time_step_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            forecast_csv = Path(tmp) / "forecast.csv"
            pd.DataFrame({"Forecast_Rainfall_mmh": [10.0, 10.0]}).to_csv(forecast_csv, index=False)

            result = run_forecast(
                params=[1e-6, 0.1, 0.2, 3.0, 1.0, 1.0, 0.2],
                area=10.0,
                dt=0.5,
                fcst_csv_path=forecast_csv,
            )

            self.assertAlmostEqual(result["total_rainfall_mm"], 10.0)


if __name__ == "__main__":
    unittest.main()

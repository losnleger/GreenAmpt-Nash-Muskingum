import tempfile
import unittest
from pathlib import Path

from generate_example_data import generate_example_data


class ExampleDataGenerationTests(unittest.TestCase):
    def test_generator_writes_calibration_and_forecast_csvs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_example_data(output_dir=Path(tmp), verbose=False)

            self.assertTrue(paths["calibration_csv"].exists())
            self.assertTrue(paths["forecast_csv"].exists())

            calibration_text = paths["calibration_csv"].read_text(encoding="utf-8-sig").splitlines()[0]
            forecast_text = paths["forecast_csv"].read_text(encoding="utf-8-sig").splitlines()[0]
            self.assertIn("Split", calibration_text)
            self.assertIn("Forecast_Rainfall_mmh", forecast_text)


if __name__ == "__main__":
    unittest.main()

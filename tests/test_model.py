"""
Tests for forecasting module.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.forecaster import ITLaborForecaster

MODEL_CONFIG = {
    "forecast_years": 3,
    "test_size": 0.2,
    "random_seed": 42,
}


def make_timeseries(country="DE", dataset="test", n=10, trend=5.0):
    years = list(range(2014, 2014 + n))
    values = [100 + i * trend + np.random.normal(0, 1) for i in range(n)]
    return pd.DataFrame({
        "country_code": [country] * n,
        "country": ["Germany"] * n,
        "year": years,
        "value": values,
        "dataset": [dataset] * n,
    })


class TestITLaborForecaster(unittest.TestCase):

    def setUp(self):
        self.proc_tmp = tempfile.mkdtemp()
        self.models_tmp = tempfile.mkdtemp()
        self.forecaster = ITLaborForecaster(
            config=MODEL_CONFIG,
            processed_dir=Path(self.proc_tmp),
            models_dir=Path(self.models_tmp),
        )

    def test_successful_forecast(self):
        df = make_timeseries()
        result = self.forecaster.forecast_country(df, "DE", "test")
        self.assertTrue(result.success)
        self.assertFalse(result.forecast_df.empty)

    def test_forecast_has_correct_years(self):
        df = make_timeseries(n=10)
        result = self.forecaster.forecast_country(df, "DE", "test")
        forecast_rows = result.forecast_df[result.forecast_df["type"] == "forecast"]
        self.assertEqual(len(forecast_rows), MODEL_CONFIG["forecast_years"])

    def test_insufficient_data_returns_error(self):
        df = make_timeseries(n=2)
        result = self.forecaster.forecast_country(df, "DE", "test")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_r2_score_in_result(self):
        df = make_timeseries(n=12, trend=10.0)
        result = self.forecaster.forecast_country(df, "DE", "test")
        self.assertTrue(result.success)
        self.assertIsInstance(result.r2_score, float)

    def test_run_all_multiple_countries(self):
        frames = []
        for country in ["DE", "NL", "IE"]:
            frames.append(make_timeseries(country=country, dataset="isoc_sks_itsps"))
        df = pd.concat(frames, ignore_index=True)
        results = self.forecaster.run_all(df)
        self.assertEqual(len(results), 3)
        self.assertTrue(any(r.success for r in results))

    def test_metrics_csv_saved(self):
        df = make_timeseries()
        self.forecaster.run_all(df)
        self.assertTrue((Path(self.models_tmp) / "model_metrics.csv").exists())

    def test_empty_timeseries_returns_empty_list(self):
        results = self.forecaster.run_all(pd.DataFrame())
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

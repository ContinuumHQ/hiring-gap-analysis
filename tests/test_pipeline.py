"""
Tests for cleaning and feature engineering modules.
"""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.cleaner import DataCleaner
from pipeline.features import FeatureEngineer


MOCK_BA_JOBS = [
    {"hashId": "abc1", "titel": "Python Dev", "arbeitgeber": "TechCo",
     "aktuelleVeroeffentlichungsdatum": "2024-01-15", "angebotsart": "1"},
    {"hashId": "abc2", "titel": "Data Engineer", "arbeitgeber": "DataCo",
     "aktuelleVeroeffentlichungsdatum": "2024-01-16", "angebotsart": "1"},
    {"hashId": "abc1", "titel": "Python Dev", "arbeitgeber": "TechCo",
     "aktuelleVeroeffentlichungsdatum": "2024-01-15", "angebotsart": "1"},  # duplicate
]


class TestDataCleaner(unittest.TestCase):

    def setUp(self):
        self.raw_tmp = tempfile.mkdtemp()
        self.proc_tmp = tempfile.mkdtemp()
        self.ba_dir = Path(self.raw_tmp) / "bundesagentur"
        self.ba_dir.mkdir()
        self.cleaner = DataCleaner(Path(self.raw_tmp), Path(self.proc_tmp))

    def _write_ba_file(self, jobs, code="43444", region="Bayern"):
        path = self.ba_dir / f"BA_{code}_{region}.json"
        with open(path, "w") as f:
            json.dump(jobs, f)

    def test_deduplication(self):
        self._write_ba_file(MOCK_BA_JOBS)
        df = self.cleaner.clean_bundesagentur()
        self.assertEqual(len(df), 1)

    def test_output_csv_created(self):
        self._write_ba_file(MOCK_BA_JOBS)
        self.cleaner.clean_bundesagentur()
        self.assertTrue((Path(self.proc_tmp) / "bundesagentur_clean.csv").exists())

    def test_empty_dir_returns_empty_df(self):
        df = self.cleaner.clean_bundesagentur()
        self.assertTrue(df.empty)

    def test_malformed_json_skipped(self):
        bad_path = self.ba_dir / "BA_43444_Berlin.json"
        bad_path.write_text("not valid json")
        df = self.cleaner.clean_bundesagentur()
        self.assertTrue(df.empty or len(df) == 0)

    def test_occupation_label_mapped(self):
        self._write_ba_file(MOCK_BA_JOBS, code="43444")
        df = self.cleaner.clean_bundesagentur()
        self.assertIn("Software Development", df["occupation_label"].values)


class TestFeatureEngineer(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.engineer = FeatureEngineer(Path(self.tmp))

    def _make_job_df(self):
        return pd.DataFrame({
            "job_id": ["1", "2", "3", "4"],
            "occupation_label": ["Software Development", "Software Development",
                                  "Data Engineering / Databases", "IT Consulting"],
            "region": ["Bayern", "Berlin", "Bayern", "Berlin"],
            "employer": ["A", "B", "C", "D"],
        })

    def test_job_features_aggregated(self):
        df = self._make_job_df()
        result = self.engineer.build_job_features(df)
        self.assertFalse(result.empty)
        self.assertIn("job_count", result.columns)
        self.assertIn("occupation_share_pct", result.columns)

    def test_occupation_share_sums_to_100_per_region(self):
        df = self._make_job_df()
        result = self.engineer.build_job_features(df)
        for region, group in result.groupby("region"):
            self.assertAlmostEqual(group["occupation_share_pct"].sum(), 100.0, places=1)

    def test_empty_df_returns_empty(self):
        result = self.engineer.build_job_features(pd.DataFrame())
        self.assertTrue(result.empty)

    def test_country_comparison_with_empty_returns_empty(self):
        result = self.engineer.build_country_comparison({})
        self.assertTrue(result.empty)

    def test_timeseries_has_yoy_growth(self):
        df = pd.DataFrame({
            "country_code": ["DE"] * 4,
            "country": ["Germany"] * 4,
            "year": [2020, 2021, 2022, 2023],
            "value": [100, 110, 120, 130],
            "dataset": ["test"] * 4,
        })
        result = self.engineer.build_timeseries({"test": df})
        self.assertIn("yoy_growth", result.columns)


if __name__ == "__main__":
    unittest.main(verbosity=2)

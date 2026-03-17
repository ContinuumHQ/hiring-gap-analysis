"""
Tests for ingestion modules.
Uses mocking to avoid real API calls.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.bundesagentur import BundesagenturClient, FetchResult
from ingestion.eurostat import EurostatClient


BA_CONFIG = {
    "occupation_codes": ["43444"],
    "regions": ["Bayern"],
    "max_results_per_query": 10,
    "request_timeout_seconds": 5,
    "retry_attempts": 2,
    "retry_delay_seconds": 0,
}

ES_CONFIG = {
    "datasets": {"isoc_sks_itsps": "isoc_sks_itsps"},
    "countries": ["DE", "NL"],
    "request_timeout_seconds": 5,
    "retry_attempts": 2,
    "retry_delay_seconds": 0,
}

MOCK_BA_RESPONSE = {
    "stellenangebote": [
        {"hashId": "abc123", "titel": "Python Developer", "arbeitgeber": "TechCo"},
        {"hashId": "def456", "titel": "Data Engineer", "arbeitgeber": "DataCo"},
    ],
    "maxErgebnisse": 2,
}

MOCK_ES_RESPONSE = {
    "id": ["geo", "time"],
    "size": [2, 3],
    "dimension": {
        "geo": {
            "category": {
                "index": {"DE": 0, "NL": 1},
                "label": {"DE": "Germany", "NL": "Netherlands"},
            }
        },
        "time": {
            "category": {
                "index": {"2021": 0, "2022": 1, "2023": 2},
                "label": {"2021": "2021", "2022": "2022", "2023": "2023"},
            }
        },
    },
    "value": {"0": 100, "1": 110, "2": 120, "3": 80, "4": 85, "5": 90},
}


class TestBundesagenturClient(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.client = BundesagenturClient(BA_CONFIG, Path(self.tmp))

    @patch("ingestion.bundesagentur.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_BA_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = self.client.fetch_by_occupation("43444", "Bayern")

        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 2)
        self.assertEqual(result.total_found, 2)

    @patch("ingestion.bundesagentur.requests.get")
    def test_timeout_retries(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = self.client.fetch_by_occupation("43444")

        self.assertFalse(result.success)
        self.assertIn("failed", result.error.lower())
        self.assertEqual(mock_get.call_count, BA_CONFIG["retry_attempts"])

    @patch("ingestion.bundesagentur.requests.get")
    def test_http_404_no_retry(self, mock_get):
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_get.side_effect = http_err

        result = self.client.fetch_by_occupation("99999")

        self.assertFalse(result.success)
        self.assertEqual(mock_get.call_count, 1)

    @patch("ingestion.bundesagentur.requests.get")
    def test_raw_file_saved(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_BA_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        self.client.fetch_by_occupation("43444", "Bayern")

        saved = list(Path(self.tmp).glob("*.json"))
        self.assertEqual(len(saved), 1)

    def test_fetch_result_defaults(self):
        result = FetchResult(success=True)
        self.assertEqual(result.data, [])
        self.assertIsNone(result.error)


class TestEurostatClient(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.client = EurostatClient(ES_CONFIG, Path(self.tmp))

    @patch("ingestion.eurostat.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_ES_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = self.client.fetch_dataset("isoc_sks_itsps")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.df)
        self.assertFalse(result.df.empty)
        self.assertIn("country_code", result.df.columns)
        self.assertIn("year", result.df.columns)
        self.assertIn("value", result.df.columns)

    @patch("ingestion.eurostat.requests.get")
    def test_connection_error_retries(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("unreachable")

        result = self.client.fetch_dataset("isoc_sks_itsps")

        self.assertFalse(result.success)
        self.assertEqual(mock_get.call_count, ES_CONFIG["retry_attempts"])

    @patch("ingestion.eurostat.requests.get")
    def test_parsed_values_correct(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_ES_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = self.client.fetch_dataset("isoc_sks_itsps")

        de_rows = result.df[result.df["country_code"] == "DE"]
        self.assertEqual(len(de_rows), 3)
        self.assertEqual(sorted(de_rows["value"].tolist()), [100, 110, 120])


if __name__ == "__main__":
    unittest.main(verbosity=2)

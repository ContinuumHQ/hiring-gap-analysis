"""
Eurostat API - ICT labor market data ingestion.
Fetches employment statistics for IT specialists across European countries.

API docs: https://wikis.ec.europa.eu/display/EUROSTATHELP/API+Statistics
No authentication required.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


@dataclass
class EurostatResult:
    success: bool
    dataset: str = ""
    df: Optional[pd.DataFrame] = None
    error: Optional[str] = None


class EurostatClient:
    def __init__(self, config: dict, raw_dir: Path) -> None:
        self.config = config
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = config.get("request_timeout_seconds", 15)
        self.retries = config.get("retry_attempts", 3)
        self.retry_delay = config.get("retry_delay_seconds", 3)
        self.countries = config.get("countries", ["DE"])

    def _get(self, dataset_id: str, params: dict) -> dict:
        url = f"{BASE_URL}/{dataset_id}"
        for attempt in range(1, self.retries + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning("Attempt %d/%d - Timeout: %s", attempt, self.retries, dataset_id)
            except requests.exceptions.ConnectionError as e:
                logger.warning("Attempt %d/%d - Connection error: %s", attempt, self.retries, e)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else "unknown"
                logger.warning("Attempt %d/%d - HTTP %s: %s", attempt, self.retries, status, dataset_id)
                if e.response and e.response.status_code == 404:
                    raise RuntimeError(f"Dataset not found: {dataset_id}") from e
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Attempt %d/%d - Parse error: %s", attempt, self.retries, e)
            if attempt < self.retries:
                time.sleep(self.retry_delay)
        raise RuntimeError(f"All {self.retries} attempts failed for dataset: {dataset_id}")

    def _parse_response(self, raw: dict, dataset_id: str) -> pd.DataFrame:
        try:
            dims = raw.get("dimension", {})
            values = raw.get("value", {})
            if not dims or not values:
                raise ValueError("Empty or malformed response")

            time_dim = dims.get("time", {}).get("category", {}).get("index", {})
            geo_dim = dims.get("geo", {}).get("category", {}).get("index", {})
            geo_labels = dims.get("geo", {}).get("category", {}).get("label", {})

            time_list = sorted(time_dim.keys(), key=lambda x: time_dim[x])
            geo_list = sorted(geo_dim.keys(), key=lambda x: geo_dim[x])
            n_time = len(time_list)

            rows = []
            for g_idx, geo in enumerate(geo_list):
                for t_idx, year_str in enumerate(time_list):
                    flat_idx = g_idx * n_time + t_idx
                    val = values.get(str(flat_idx))
                    # Handle quarterly format (2001-Q1) - use year only
                    try:
                        year = int(year_str[:4])
                    except (ValueError, TypeError):
                        continue
                    rows.append({
                        "country_code": geo,
                        "country": geo_labels.get(geo, geo),
                        "year": year,
                        "value": val,
                        "dataset": dataset_id,
                    })

            df = pd.DataFrame(rows)
            df = df[df["value"].notna()]
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df.dropna(subset=["value"])

        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to parse dataset {dataset_id}: {e}") from e

    def fetch_dataset(self, dataset_id: str) -> EurostatResult:
        logger.info("Fetching Eurostat dataset: %s", dataset_id)
        params = {"geo": self.countries, "format": "JSON", "lang": "EN"}
        try:
            raw = self._get(dataset_id, params)
            self._save_raw(raw, dataset_id)
            df = self._parse_response(raw, dataset_id)
            logger.info("  -> %d rows fetched for %d countries", len(df), df["country_code"].nunique())
            return EurostatResult(success=True, dataset=dataset_id, df=df)
        except RuntimeError as e:
            logger.error("  -> Fetch failed: %s", e)
            return EurostatResult(success=False, dataset=dataset_id, error=str(e))
        except ValueError as e:
            logger.error("  -> Parse failed: %s", e)
            return EurostatResult(success=False, dataset=dataset_id, error=str(e))

    def fetch_all(self) -> list:
        datasets = list(self.config.get("datasets", {}).values())
        results = []
        for dataset_id in datasets:
            result = self.fetch_dataset(dataset_id)
            results.append(result)
            time.sleep(1.0)
        successful = sum(1 for r in results if r.success)
        logger.info("Eurostat fetch complete: %d/%d successful", successful, len(results))
        return results

    def _save_raw(self, data: dict, dataset_id: str) -> None:
        path = self.raw_dir / f"eurostat_{dataset_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug("Raw data saved: %s", path)

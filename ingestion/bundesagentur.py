"""
Bundesagentur fuer Arbeit - Job listings ingestion.
Fetches IT job postings from the official Jobboerse API.

API docs: https://jobsuche.api.bund.dev/
No authentication required.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "Accept": "application/json",
}


@dataclass
class FetchResult:
    """Result of a single API fetch operation."""
    success: bool
    data: list = field(default_factory=list)
    total_found: int = 0
    error: Optional[str] = None
    source: str = ""


class BundesagenturClient:
    """
    Client for the Bundesagentur fuer Arbeit Jobboerse API.

    Fetches IT job postings by occupation code and region.
    Implements retry logic and structured error handling.

    Parameters
    ----------
    config : dict
        Configuration dict from config.yaml (bundesagentur section).
    raw_dir : Path
        Directory to save raw JSON responses.
    """

    def __init__(self, config: dict, raw_dir: Path) -> None:
        self.config = config
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = config.get("request_timeout_seconds", 10)
        self.retries = config.get("retry_attempts", 3)
        self.retry_delay = config.get("retry_delay_seconds", 2)

    def _get(self, params: dict) -> FetchResult:
        """
        Execute a single GET request with retry logic.

        Parameters
        ----------
        params : dict
            Query parameters for the API call.

        Returns
        -------
        FetchResult
            Result object with data or error information.
        """
        for attempt in range(1, self.retries + 1):
            try:
                response = requests.get(
                    BASE_URL,
                    headers=HEADERS,
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                jobs = data.get("stellenangebote", [])
                total = data.get("maxErgebnisse", 0)
                return FetchResult(success=True, data=jobs, total_found=total)

            except requests.exceptions.Timeout:
                logger.warning("Attempt %d/%d - Timeout for params: %s", attempt, self.retries, params)
            except requests.exceptions.ConnectionError as e:
                logger.warning("Attempt %d/%d - Connection error: %s", attempt, self.retries, e)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else "unknown"
                logger.warning("Attempt %d/%d - HTTP %s", attempt, self.retries, status)
                if e.response and 400 <= e.response.status_code < 500:
                    return FetchResult(success=False, error=f"HTTP {status} - not retrying")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Attempt %d/%d - Parse error: %s", attempt, self.retries, e)
                return FetchResult(success=False, error=f"Parse error: {e}")

            if attempt < self.retries:
                time.sleep(self.retry_delay)

        return FetchResult(success=False, error=f"All {self.retries} attempts failed")

    def fetch_by_occupation(self, occupation_code: str, region: Optional[str] = None) -> FetchResult:
        """
        Fetch job listings for a specific occupation code.

        Parameters
        ----------
        occupation_code : str
            KldB occupation code (e.g. '43444' for software development).
        region : str, optional
            German state name to filter by region.

        Returns
        -------
        FetchResult
            Fetched job listings with metadata.
        """
        params = {
            "berufId": occupation_code,
            "size": self.config.get("max_results_per_query", 100),
            "page": 1,
        }
        if region:
            params["arbeitsort.region"] = region

        source = f"BA_{occupation_code}_{region or 'all'}"
        logger.info("Fetching: occupation=%s region=%s", occupation_code, region or "all")

        result = self._get(params)
        result.source = source

        if result.success:
            logger.info("  -> %d jobs fetched (total available: %d)", len(result.data), result.total_found)
            self._save_raw(result.data, source)
        else:
            logger.error("  -> Failed: %s", result.error)

        return result

    def fetch_all(self) -> list:
        """
        Fetch all configured occupation codes across all regions.

        Returns
        -------
        list[FetchResult]
            List of results for each occupation/region combination.
        """
        results = []
        codes = self.config.get("occupation_codes", [])
        regions = self.config.get("regions", [None])

        total = len(codes) * len(regions)
        logger.info("Starting full fetch: %d codes x %d regions = %d requests", len(codes), len(regions), total)

        for code in codes:
            for region in regions:
                result = self.fetch_by_occupation(code, region)
                results.append(result)
                time.sleep(0.5)

        successful = sum(1 for r in results if r.success)
        logger.info("Fetch complete: %d/%d successful", successful, total)
        return results

    def _save_raw(self, data: list, source: str) -> None:
        """Save raw API response to disk."""
        path = self.raw_dir / f"{source}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug("Raw data saved: %s (%d records)", path, len(data))


def load_config(config_path: Path = Path("config.yaml")) -> dict:
    """Load and validate configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if "bundesagentur" not in config:
        raise KeyError("Missing 'bundesagentur' section in config.yaml")
    return config

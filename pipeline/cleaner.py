"""
Data cleaning module.
Standardizes and merges raw data from Bundesagentur and Eurostat.
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

OCCUPATION_LABELS = {
    "43444": "Software Development",
    "43414": "IT System Administration",
    "43434": "Data Engineering / Databases",
    "43424": "IT Consulting",
    "43494": "Other IT Roles",
}


class DataCleaner:
    def __init__(self, raw_dir: Path, processed_dir: Path) -> None:
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def clean_bundesagentur(self) -> pd.DataFrame:
        ba_dir = self.raw_dir / "bundesagentur"
        if not ba_dir.exists():
            logger.warning("No Bundesagentur raw data found at %s", ba_dir)
            return pd.DataFrame()

        files = list(ba_dir.glob("BA_*.json"))
        if not files:
            logger.warning("No BA JSON files found")
            return pd.DataFrame()

        rows = []
        for path in files:
            parts = path.stem.split("_")
            occupation_code = parts[1] if len(parts) > 1 else "unknown"
            region = parts[2] if len(parts) > 2 else "unknown"

            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)

                if isinstance(raw, dict):
                    jobs = raw.get("stellenangebote", [])
                elif isinstance(raw, list):
                    jobs = raw
                else:
                    logger.warning("Unexpected format in %s", path.name)
                    continue

                REGION_NORMALIZE = {
                        "Baden-Wuerttemberg": "Baden-Württemberg",
                    }
                for job in jobs:
                    raw_region = job.get("arbeitsort", {}).get("region", region)
                    clean_region = REGION_NORMALIZE.get(raw_region, raw_region)
                    rows.append({
                        "job_id": f"{job.get('refnr', '')}_{occupation_code}",
                        "refnr": job.get("refnr", ""),
                        "title": job.get("titel", ""),
                        "employer": job.get("arbeitgeber", ""),
                        "location": job.get("arbeitsort", {}).get("ort", ""),
                        "region": clean_region,
                        "occupation_code": occupation_code,
                        "occupation_label": OCCUPATION_LABELS.get(occupation_code, occupation_code),
                        "published_date": job.get("aktuelleVeroeffentlichungsdatum", ""),
                        "source": "bundesagentur",
                    })

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Failed to parse %s: %s", path.name, e)
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = df.drop_duplicates(subset=["job_id"])
        df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
        df = df.dropna(subset=["refnr", "title"])
        df = df[df["title"].str.strip() != ""]

        out_path = self.processed_dir / "bundesagentur_clean.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")
        logger.info("Bundesagentur cleaned: %d jobs -> %s", len(df), out_path)
        return df

    def clean_eurostat(self) -> dict:
        files = list(self.raw_dir.glob("eurostat_*.json"))
        if not files:
            logger.warning("No Eurostat raw data found")
            return {}

        results = {}
        for path in files:
            dataset_id = path.stem.replace("eurostat_", "")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                df = self._parse_eurostat_json(raw, dataset_id)
                if df.empty:
                    continue
                out_path = self.processed_dir / f"eurostat_{dataset_id}_clean.csv"
                df.to_csv(out_path, index=False, encoding="utf-8")
                logger.info("Eurostat %s cleaned: %d rows -> %s", dataset_id, len(df), out_path)
                results[dataset_id] = df
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to clean %s: %s", dataset_id, e)
                continue

        return results

    def _parse_eurostat_json(self, raw: dict, dataset_id: str) -> pd.DataFrame:
        try:
            dims = raw.get("dimension", {})
            values = raw.get("value", {})
            if not dims or not values:
                return pd.DataFrame()

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
            logger.warning("Parse error for %s: %s", dataset_id, e)
            return pd.DataFrame()

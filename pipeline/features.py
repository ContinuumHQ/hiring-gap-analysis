"""
Feature engineering module.
Builds analysis-ready datasets from cleaned data.
"""

import logging
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Builds features for analysis and modeling.

    Parameters
    ----------
    processed_dir : Path
        Directory with cleaned CSVs.
    """

    def __init__(self, processed_dir: Path) -> None:
        self.processed_dir = Path(processed_dir)

    def build_job_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build aggregated job market features from Bundesagentur data.

        Parameters
        ----------
        df : pd.DataFrame
            Cleaned Bundesagentur job listings.

        Returns
        -------
        pd.DataFrame
            Aggregated features by occupation and region.
        """
        if df.empty:
            logger.warning("Empty DataFrame - skipping job features")
            return pd.DataFrame()

        agg = df.groupby(["occupation_label", "region"]).agg(
            job_count=("job_id", "count"),
            unique_employers=("employer", "nunique"),
        ).reset_index()

        # Share of each occupation per region
        region_totals = agg.groupby("region")["job_count"].transform("sum")
        agg["occupation_share_pct"] = (agg["job_count"] / region_totals * 100).round(2)

        out_path = self.processed_dir / "job_features.csv"
        agg.to_csv(out_path, index=False, encoding="utf-8")
        logger.info("Job features built: %d rows -> %s", len(agg), out_path)
        return agg

    def build_country_comparison(self, eurostat_dfs: dict) -> pd.DataFrame:
        """
        Build country-level comparison features from Eurostat data.

        Parameters
        ----------
        eurostat_dfs : dict
            Dictionary of dataset_id -> cleaned DataFrame.

        Returns
        -------
        pd.DataFrame
            Wide-format country comparison table.
        """
        if not eurostat_dfs:
            logger.warning("No Eurostat data - skipping country comparison")
            return pd.DataFrame()

        all_dfs = []
        for dataset_id, df in eurostat_dfs.items():
            if df.empty:
                continue
            latest_year = df["year"].max()
            latest = df[df["year"] == latest_year].copy()
            latest = latest.rename(columns={"value": dataset_id})
            latest = latest[["country_code", "country", "year", dataset_id]]
            all_dfs.append(latest)

        if not all_dfs:
            return pd.DataFrame()

        merged = all_dfs[0]
        for df in all_dfs[1:]:
            merged = merged.merge(
                df[["country_code"] + [c for c in df.columns if c not in merged.columns]],
                on="country_code",
                how="outer"
            )

        # Normalize: Germany = 100 index
        numeric_cols = [c for c in merged.columns if c not in ["country_code", "country", "year"]]
        de_row = merged[merged["country_code"] == "DE"]

        for col in numeric_cols:
            if not de_row.empty and pd.notna(de_row[col].values[0]) and de_row[col].values[0] != 0:
                de_val = de_row[col].values[0]
                merged[f"{col}_index_de100"] = (merged[col] / de_val * 100).round(1)

        out_path = self.processed_dir / "country_comparison.csv"
        merged.to_csv(out_path, index=False, encoding="utf-8")
        logger.info("Country comparison built: %d countries -> %s", len(merged), out_path)
        return merged

    def build_timeseries(self, eurostat_dfs: dict) -> pd.DataFrame:
        """
        Build long-format time series for forecasting.

        Parameters
        ----------
        eurostat_dfs : dict
            Dictionary of dataset_id -> cleaned DataFrame.

        Returns
        -------
        pd.DataFrame
            Long-format time series with country, year, value.
        """
        if not eurostat_dfs:
            return pd.DataFrame()

        frames = list(eurostat_dfs.values())
        if not frames:
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        df = df.sort_values(["country_code", "dataset", "year"])

        # Year-over-year growth rate
        df["yoy_growth"] = df.groupby(["country_code", "dataset"])["value"].pct_change() * 100

        out_path = self.processed_dir / "timeseries.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")
        logger.info("Time series built: %d rows -> %s", len(df), out_path)
        return df

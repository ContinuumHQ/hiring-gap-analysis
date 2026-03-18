"""
hiring-gap-analysis - Main entry point.
End-to-end pipeline: API ingestion -> cleaning -> features -> model -> dashboard.

Usage:
    python main.py                  # Full pipeline
    python main.py --skip-fetch     # Use existing raw data (skip API calls)
    python main.py --skip-model     # Skip forecasting
    python main.py --no-report      # No HTML report
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def load_config(path: Path = Path("config.yaml")) -> dict:
    """Load configuration file with validation."""
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    required = ["bundesagentur", "eurostat", "data", "output", "model"]
    missing = [k for k in required if k not in config]
    if missing:
        raise KeyError(f"Missing config sections: {missing}")
    return config


def header(title: str) -> None:
    logger.info("=" * 60)
    logger.info("  %s", title)
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="IT Hiring Gap Analysis Pipeline")
    parser.add_argument("--skip-fetch",  action="store_true", help="Use existing raw data")
    parser.add_argument("--skip-model",  action="store_true", help="Skip forecasting step")
    parser.add_argument("--no-report",   action="store_true", help="Skip HTML report generation")
    parser.add_argument("--config",      type=str, default="config.yaml")
    args = parser.parse_args()

    config = load_config(Path(args.config))

    raw_dir       = Path(config["data"]["raw_dir"])
    processed_dir = Path(config["data"]["processed_dir"])
    models_dir    = Path(config["data"]["models_dir"])
    plots_dir     = Path(config["output"]["plots_dir"])
    reports_dir   = Path(config["output"]["reports_dir"])

    for d in [raw_dir, processed_dir, models_dir, plots_dir, reports_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1 - Data Ingestion
    # ------------------------------------------------------------------
    header("Step 1/4 - Data Ingestion")

    ba_results = []
    eurostat_results = []

    if not args.skip_fetch:
        from ingestion.bundesagentur import BundesagenturClient
        from ingestion.eurostat import EurostatClient

        ba_client = BundesagenturClient(
            config=config["bundesagentur"],
            raw_dir=raw_dir / "bundesagentur",
        )
        ba_results = ba_client.fetch_all()
        ba_ok = sum(1 for r in ba_results if r.success)
        logger.info("Bundesagentur: %d/%d requests successful", ba_ok, len(ba_results))

        es_client = EurostatClient(
            config=config["eurostat"],
            raw_dir=raw_dir,
        )
        eurostat_results = es_client.fetch_all()
        es_ok = sum(1 for r in eurostat_results if r.success)
        logger.info("Eurostat: %d/%d datasets successful", es_ok, len(eurostat_results))
    else:
        logger.info("Skipping fetch - using existing raw data")

    # ------------------------------------------------------------------
    # Step 2 - Data Cleaning & Feature Engineering
    # ------------------------------------------------------------------
    header("Step 2/4 - Cleaning & Feature Engineering")

    from pipeline.cleaner import DataCleaner
    from pipeline.features import FeatureEngineer

    cleaner = DataCleaner(raw_dir=raw_dir, processed_dir=processed_dir)
    ba_df = cleaner.clean_bundesagentur()
    eurostat_dfs = cleaner.clean_eurostat()

    engineer = FeatureEngineer(processed_dir=processed_dir)
    job_features = engineer.build_job_features(ba_df)
    country_comparison = engineer.build_country_comparison(eurostat_dfs)
    timeseries = engineer.build_timeseries(eurostat_dfs)

    # ------------------------------------------------------------------
    # Step 3 - Forecasting
    # ------------------------------------------------------------------
    import pandas as pd

    forecast_results = []
    forecasts_df = pd.DataFrame()

    if not args.skip_model and not timeseries.empty:
        header("Step 3/4 - Forecasting")
        from model.forecaster import ITLaborForecaster

        forecaster = ITLaborForecaster(
            config=config["model"],
            processed_dir=processed_dir,
            models_dir=models_dir,
        )
        forecast_results = forecaster.run_all(timeseries)
        successful = sum(1 for r in forecast_results if r.success)
        logger.info("Forecasts: %d/%d successful", successful, len(forecast_results))

        forecasts_path = models_dir / "forecasts.csv"
        if forecasts_path.exists():
            forecasts_df = pd.read_csv(forecasts_path)
    else:
        logger.info("Skipping forecast step")

    # ------------------------------------------------------------------
    # Step 4 - Dashboard & Report
    # ------------------------------------------------------------------
    header("Step 4/4 - Dashboard & Report")

    from dashboard.visualizer import DashboardVisualizer
    from dashboard.report import generate_html_report

    viz = DashboardVisualizer(plots_dir=plots_dir)
    plots = viz.generate_all(job_features, country_comparison, timeseries, forecasts_df)
    logger.info("%d plots generated", len(plots))

    if not args.no_report:
        metrics_path = models_dir / "model_metrics.csv"
        model_metrics = pd.read_csv(metrics_path) if metrics_path.exists() else pd.DataFrame()

        report_path = generate_html_report(
            job_features=job_features,
            country_comparison=country_comparison,
            model_metrics=model_metrics,
            plots_dir=plots_dir,
            reports_dir=reports_dir,
        )
        logger.info("Report: %s", report_path)

    header("Pipeline complete")
    logger.info("Plots   : %s", plots_dir)
    logger.info("Reports : %s", reports_dir)
    logger.info("Log     : pipeline.log")


if __name__ == "__main__":
    main()
    
# PDF Report
try:
    from dashboard.pdf_reporter import generate_pdf_report
    import pandas as pd
    metrics_path = Path("data/models/model_metrics.csv")
    model_metrics = pd.read_csv(metrics_path) if metrics_path.exists() else pd.DataFrame()
    pdf_path = generate_pdf_report(
        job_features=pd.read_csv("data/processed/job_features.csv"),
        country_comparison=pd.read_csv("data/processed/country_comparison.csv"),
        model_metrics=model_metrics,
        plots_dir=Path("docs/plots"),
        reports_dir=Path("docs/reports"),
    )
    if pdf_path:
        print(f"PDF Report: {pdf_path}")
except Exception as e:
    print(f"PDF generation skipped: {e}")

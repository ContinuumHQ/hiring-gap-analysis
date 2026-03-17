"""
Forecasting module.
Predicts IT job vacancy trends using linear regression and polynomial features.
Forecasts the skills gap development for Germany vs. comparable EU countries.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Result of a single country/dataset forecast."""
    country_code: str
    dataset: str
    model_name: str
    r2_score: float
    mae: float
    forecast_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: Optional[str] = None
    success: bool = True


class ITLaborForecaster:
    """
    Forecasts IT labor market trends per country.

    Uses polynomial regression to capture non-linear growth trends.
    Trained on Eurostat time series data.

    Parameters
    ----------
    config : dict
        Model configuration (forecast_years, test_size, random_seed).
    processed_dir : Path
        Directory with processed CSVs.
    models_dir : Path
        Directory to save model outputs.
    """

    def __init__(self, config: dict, processed_dir: Path, models_dir: Path) -> None:
        self.config = config
        self.processed_dir = Path(processed_dir)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.forecast_years = config.get("forecast_years", 5)
        self.test_size = config.get("test_size", 0.2)

    def _build_model(self, degree: int = 2) -> Pipeline:
        """Build a polynomial regression pipeline."""
        return Pipeline([
            ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
            ("reg", LinearRegression()),
        ])

    def forecast_country(self, df: pd.DataFrame, country_code: str, dataset: str) -> ForecastResult:
        """
        Fit model and generate forecast for a single country/dataset.

        Parameters
        ----------
        df : pd.DataFrame
            Time series data for this country and dataset.
        country_code : str
            ISO country code.
        dataset : str
            Eurostat dataset identifier.

        Returns
        -------
        ForecastResult
            Forecast with metrics and projected values.
        """
        series = df[["year", "value"]].dropna().sort_values("year")

        if len(series) < 4:
            return ForecastResult(
                country_code=country_code,
                dataset=dataset,
                model_name="polynomial_deg2",
                r2_score=float("nan"),
                mae=float("nan"),
                error=f"Insufficient data: {len(series)} points (need >= 4)",
                success=False,
            )

        X = series["year"].values.reshape(-1, 1)
        y = series["value"].values

        split = max(1, int(len(X) * (1 - self.test_size)))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        try:
            model = self._build_model(degree=2)
            model.fit(X_train, y_train)

            y_pred_test = model.predict(X_test) if len(X_test) > 0 else np.array([])
            r2 = r2_score(y_test, y_pred_test) if len(y_test) > 0 else float("nan")
            mae = mean_absolute_error(y_test, y_pred_test) if len(y_test) > 0 else float("nan")

            last_year = int(series["year"].max())
            future_years = np.arange(last_year + 1, last_year + self.forecast_years + 1).reshape(-1, 1)
            future_values = model.predict(future_years)

            # Historical fitted values
            fitted = model.predict(X)

            hist_df = pd.DataFrame({
                "year": series["year"].values,
                "actual": y,
                "fitted": fitted,
                "type": "historical",
                "country_code": country_code,
                "dataset": dataset,
            })

            forecast_df_future = pd.DataFrame({
                "year": future_years.flatten(),
                "actual": np.nan,
                "fitted": future_values,
                "type": "forecast",
                "country_code": country_code,
                "dataset": dataset,
            })

            full_df = pd.concat([hist_df, forecast_df_future], ignore_index=True)

            logger.info(
                "Forecast %s/%s: R2=%.3f MAE=%.1f forecast_end=%d",
                country_code, dataset, r2, mae, last_year + self.forecast_years
            )

            return ForecastResult(
                country_code=country_code,
                dataset=dataset,
                model_name="polynomial_deg2",
                r2_score=round(r2, 4),
                mae=round(mae, 2),
                forecast_df=full_df,
                success=True,
            )

        except (ValueError, np.linalg.LinAlgError) as e:
            logger.error("Model failed for %s/%s: %s", country_code, dataset, e)
            return ForecastResult(
                country_code=country_code,
                dataset=dataset,
                model_name="polynomial_deg2",
                r2_score=float("nan"),
                mae=float("nan"),
                error=str(e),
                success=False,
            )

    def run_all(self, timeseries_df: pd.DataFrame) -> list:
        """
        Run forecasts for all country/dataset combinations.

        Parameters
        ----------
        timeseries_df : pd.DataFrame
            Long-format time series from features module.

        Returns
        -------
        list[ForecastResult]
            All forecast results.
        """
        if timeseries_df.empty:
            logger.warning("Empty time series - no forecasts generated")
            return []

        results = []
        groups = timeseries_df.groupby(["country_code", "dataset"])

        for (country, dataset), group in groups:
            result = self.forecast_country(group, country, dataset)
            results.append(result)

        # Save all forecasts combined
        all_forecasts = pd.concat(
            [r.forecast_df for r in results if r.success and not r.forecast_df.empty],
            ignore_index=True
        )
        if not all_forecasts.empty:
            out_path = self.models_dir / "forecasts.csv"
            all_forecasts.to_csv(out_path, index=False, encoding="utf-8")
            logger.info("All forecasts saved: %s", out_path)

        # Save model metrics
        metrics = [{
            "country_code": r.country_code,
            "dataset": r.dataset,
            "model": r.model_name,
            "r2": r.r2_score,
            "mae": r.mae,
            "success": r.success,
            "error": r.error,
        } for r in results]

        metrics_df = pd.DataFrame(metrics)
        metrics_path = self.models_dir / "model_metrics.csv"
        metrics_df.to_csv(metrics_path, index=False, encoding="utf-8")
        logger.info("Model metrics saved: %s", metrics_path)

        successful = sum(1 for r in results if r.success)
        logger.info("Forecasting complete: %d/%d successful", successful, len(results))
        return results

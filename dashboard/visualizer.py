"""
Visualization module.
Generates all analysis plots in GitHub dark theme style.
"""

import logging
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# GitHub dark theme colors
GH_BG        = "#0d1117"
GH_BG_CARD   = "#161b22"
GH_BORDER    = "#30363d"
GH_TEXT      = "#c9d1d9"
GH_TEXT_MUTED = "#8b949e"
GH_BLUE      = "#58a6ff"
GH_GREEN     = "#3fb950"
GH_RED       = "#f85149"
GH_ORANGE    = "#d29922"
GH_PURPLE    = "#bc8cff"
GH_CYAN      = "#39d353"

COUNTRY_COLORS = {
    "DE": GH_RED,
    "NL": GH_BLUE,
    "IE": GH_GREEN,
    "EE": GH_CYAN,
    "PL": GH_ORANGE,
    "NO": GH_PURPLE,
    "PT": "#79c0ff",
    "EU27_2020": GH_TEXT_MUTED,
}

COUNTRY_LABELS = {
    "DE": "Germany", "NL": "Netherlands", "IE": "Ireland",
    "EE": "Estonia", "PL": "Poland", "NO": "Norway",
    "PT": "Portugal", "EU27_2020": "EU Average",
}


def _apply_github_style(fig, ax):
    """Apply GitHub dark theme to a figure and axes."""
    fig.patch.set_facecolor(GH_BG)
    ax.set_facecolor(GH_BG_CARD)
    ax.tick_params(colors=GH_TEXT_MUTED, labelsize=9)
    ax.xaxis.label.set_color(GH_TEXT_MUTED)
    ax.yaxis.label.set_color(GH_TEXT_MUTED)
    ax.title.set_color(GH_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(GH_BORDER)
    ax.grid(True, color=GH_BORDER, linewidth=0.5, linestyle="--", alpha=0.6)


class DashboardVisualizer:
    """
    Creates all dashboard plots from processed data.

    Parameters
    ----------
    plots_dir : Path
        Output directory for PNG files.
    """

    def __init__(self, plots_dir: Path) -> None:
        self.plots_dir = Path(plots_dir)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        plt.rcParams.update({
            "font.family": "monospace",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
        })

    def plot_job_distribution(self, df: pd.DataFrame) -> Optional[Path]:
        """
        Grouped bar chart: IT job postings by occupation and region.
        Shows all regions side by side.
        """
        if df.empty or "occupation_label" not in df.columns:
            logger.warning("No job data - skipping job distribution plot")
            return None

        pivot = df.pivot_table(
            index="occupation_label",
            columns="region",
            values="job_id",
            aggfunc="count"
        ).fillna(0)

        if pivot.empty:
            logger.warning("Pivot table empty - skipping job distribution plot")
            return None

        n_regions = len(pivot.columns)
        region_colors = [GH_BLUE, GH_GREEN, GH_ORANGE, GH_PURPLE, GH_CYAN][:n_regions]

        fig, ax = plt.subplots(figsize=(14, 6))
        _apply_github_style(fig, ax)

        x = np.arange(len(pivot.index))
        width = 0.8 / n_regions

        for i, (region, color) in enumerate(zip(pivot.columns, region_colors)):
            offset = (i - n_regions / 2 + 0.5) * width
            bars = ax.bar(x + offset, pivot[region], width=width * 0.9,
                         label=region, color=color, alpha=0.85)
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                           str(int(h)), ha="center", va="bottom",
                           fontsize=7, color=GH_TEXT_MUTED)

        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index, rotation=20, ha="right", color=GH_TEXT)
        ax.set_title("IT Job Postings by Occupation and Region - Germany", pad=12)
        ax.set_ylabel("Number of Postings", color=GH_TEXT_MUTED)
        legend = ax.legend(title="Region", title_fontsize=8, fontsize=8,
                          facecolor=GH_BG_CARD, edgecolor=GH_BORDER,
                          labelcolor=GH_TEXT)
        legend.get_title().set_color(GH_TEXT_MUTED)

        plt.tight_layout()
        path = self.plots_dir / "01_job_distribution.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG)
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def plot_country_comparison(self, df: pd.DataFrame) -> Optional[Path]:
        """
        Horizontal bar chart: IT specialist index - Germany vs. peers.
        """
        index_cols = [c for c in df.columns if c.endswith("_index_de100")]
        if df.empty or not index_cols:
            logger.warning("No country comparison data - skipping")
            return None

        col = index_cols[0]
        plot_df = df[["country_code", col]].dropna().copy()
        plot_df["country"] = plot_df["country_code"].map(COUNTRY_LABELS).fillna(plot_df["country_code"])
        plot_df = plot_df.sort_values(col, ascending=True)

        colors = [COUNTRY_COLORS.get(c, GH_BLUE) for c in plot_df["country_code"]]

        fig, ax = plt.subplots(figsize=(11, 5))
        _apply_github_style(fig, ax)

        bars = ax.barh(plot_df["country"], plot_df[col], color=colors, alpha=0.85, height=0.6)
        ax.axvline(x=100, color=GH_TEXT_MUTED, linestyle="--", linewidth=1.2, label="Germany = 100")

        for bar, val in zip(bars, plot_df[col]):
            ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                   f"{val:.0f}", va="center", fontsize=9, color=GH_TEXT)

        ax.set_title("IT Specialist Index vs. Germany  (Germany = 100)", pad=12)
        ax.set_xlabel("Index", color=GH_TEXT_MUTED)
        ax.tick_params(axis="y", colors=GH_TEXT)
        legend = ax.legend(facecolor=GH_BG_CARD, edgecolor=GH_BORDER, labelcolor=GH_TEXT)

        plt.tight_layout()
        path = self.plots_dir / "02_country_comparison.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG)
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def plot_timeseries(self, df: pd.DataFrame) -> Optional[Path]:
        """
        Line chart: IT employment trend over time per country.
        """
        if df.empty:
            logger.warning("No time series data - skipping")
            return None

        dataset = df["dataset"].unique()[0]
        plot_df = df[df["dataset"] == dataset].copy()

        fig, ax = plt.subplots(figsize=(13, 5))
        _apply_github_style(fig, ax)

        for country in sorted(plot_df["country_code"].unique()):
            sub = plot_df[plot_df["country_code"] == country].sort_values("year")
            lw = 2.5 if country == "DE" else 1.4
            color = COUNTRY_COLORS.get(country, GH_BLUE)
            label = COUNTRY_LABELS.get(country, country)
            ax.plot(sub["year"], sub["value"], marker="o", markersize=3,
                   label=label, linewidth=lw, color=color)

        ax.set_title(f"IT Employment Trend by Country - {dataset}", pad=12)
        ax.set_xlabel("Year", color=GH_TEXT_MUTED)
        ax.set_ylabel("Value", color=GH_TEXT_MUTED)
        ax.tick_params(colors=GH_TEXT)
        legend = ax.legend(title="Country", title_fontsize=8, fontsize=8,
                          bbox_to_anchor=(1.01, 1), loc="upper left",
                          facecolor=GH_BG_CARD, edgecolor=GH_BORDER, labelcolor=GH_TEXT)
        legend.get_title().set_color(GH_TEXT_MUTED)

        plt.tight_layout()
        path = self.plots_dir / "03_timeseries.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG)
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def plot_forecast(self, forecasts_df: pd.DataFrame) -> Optional[Path]:
        """
        Line chart: Historical + forecasted IT labor market trend.
        """
        if forecasts_df.empty:
            logger.warning("No forecast data - skipping")
            return None

        dataset = forecasts_df["dataset"].unique()[0]
        plot_df = forecasts_df[forecasts_df["dataset"] == dataset].copy()

        fig, ax = plt.subplots(figsize=(13, 5))
        _apply_github_style(fig, ax)

        for country in sorted(plot_df["country_code"].unique()):
            sub = plot_df[plot_df["country_code"] == country].sort_values("year")
            hist = sub[sub["type"] == "historical"]
            fcast = sub[sub["type"] == "forecast"]
            lw = 2.5 if country == "DE" else 1.4
            color = COUNTRY_COLORS.get(country, GH_BLUE)
            label = COUNTRY_LABELS.get(country, country)
            line, = ax.plot(hist["year"], hist["fitted"], linewidth=lw,
                           color=color, label=label)
            ax.plot(fcast["year"], fcast["fitted"], linewidth=lw,
                   linestyle="--", color=color, alpha=0.7)

        forecast_start = plot_df[plot_df["type"] == "historical"]["year"].max()
        ax.axvline(x=forecast_start, color=GH_TEXT_MUTED, linestyle=":",
                  linewidth=1, label="Forecast start")

        ax.set_title(f"IT Labor Market Forecast to 2029 - {dataset}", pad=12)
        ax.set_xlabel("Year", color=GH_TEXT_MUTED)
        ax.set_ylabel("Value", color=GH_TEXT_MUTED)
        ax.tick_params(colors=GH_TEXT)
        legend = ax.legend(title="-- = forecast", title_fontsize=8, fontsize=8,
                          bbox_to_anchor=(1.01, 1), loc="upper left",
                          facecolor=GH_BG_CARD, edgecolor=GH_BORDER, labelcolor=GH_TEXT)
        legend.get_title().set_color(GH_TEXT_MUTED)

        plt.tight_layout()
        path = self.plots_dir / "04_forecast.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG)
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def generate_all(self, job_features: pd.DataFrame, country_comparison: pd.DataFrame,
                     timeseries: pd.DataFrame, forecasts: pd.DataFrame) -> list:
        """Run all plots and return list of saved paths."""
        paths = []
        for fn, args in [
            (self.plot_job_distribution, (job_features,)),
            (self.plot_country_comparison, (country_comparison,)),
            (self.plot_timeseries, (timeseries,)),
            (self.plot_forecast, (forecasts,)),
        ]:
            try:
                result = fn(*args)
                if result:
                    paths.append(result)
            except Exception as e:
                logger.error("Plot failed (%s): %s", fn.__name__, e)

        logger.info("%d plots generated", len(paths))
        return paths

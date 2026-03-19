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
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

GH_BG         = "#0d1117"
GH_BG_CARD    = "#161b22"
GH_BORDER     = "#30363d"
GH_TEXT       = "#c9d1d9"
GH_TEXT_MUTED = "#8b949e"
GH_BLUE       = "#58a6ff"
GH_GREEN      = "#3fb950"
GH_RED        = "#f85149"
GH_ORANGE     = "#d29922"
GH_PURPLE     = "#bc8cff"
GH_CYAN       = "#39d353"

COUNTRY_COLORS = {
    "DE": GH_RED, "NL": GH_BLUE, "IE": GH_GREEN,
    "EE": GH_CYAN, "PL": GH_ORANGE, "NO": GH_PURPLE,
    "PT": "#79c0ff", "EU27_2020": GH_TEXT_MUTED,
}

COUNTRY_LABELS = {
    "DE": "Germany", "NL": "Netherlands", "IE": "Ireland",
    "EE": "Estonia", "PL": "Poland", "NO": "Norway",
    "PT": "Portugal", "EU27_2020": "EU Average",
}


def _gh(fig, ax):
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
    def __init__(self, plots_dir: Path) -> None:
        self.plots_dir = Path(plots_dir)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        plt.rcParams.update({"font.family": "monospace", "font.size": 10})

    def plot_job_distribution(self, df: pd.DataFrame) -> Optional[Path]:
        if df.empty or "occupation_label" not in df.columns:
            logger.warning("No job data - skipping job distribution plot")
            return None

        if "job_count" in df.columns:
            pivot = df.pivot_table(
                index="occupation_label", columns="region",
                values="job_count", aggfunc="sum"
            ).fillna(0)
        else:
            pivot = df.groupby(["occupation_label", "region"]).size().unstack(fill_value=0)

        if pivot.empty:
            return None

        n_regions = len(pivot.columns)
        n_occ = len(pivot.index)
        fig_w = max(18, n_regions * 1.2)
        fig_h = max(6, n_occ * 1.4)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        fig.patch.set_facecolor(GH_BG)
        ax.set_facecolor(GH_BG_CARD)

        # YlOrRd for high contrast
        im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd", interpolation="nearest")

        ax.set_xticks(range(n_regions))
        ax.set_xticklabels(pivot.columns, rotation=45, ha="right", color=GH_TEXT, fontsize=12)
        ax.set_yticks(range(n_occ))
        ax.set_yticklabels(pivot.index, color=GH_TEXT, fontsize=13)

        max_val = pivot.values.max()
        for i in range(n_occ):
            for j in range(n_regions):
                val = int(pivot.values[i, j])
                if val > 0:
                    text_color = "white" if val > max_val * 0.5 else "#111111"
                    ax.text(j, i, str(val), ha="center", va="center",
                           fontsize=12, color=text_color, fontweight="bold")

        cbar = fig.colorbar(im, ax=ax, pad=0.02, shrink=0.8)
        cbar.ax.yaxis.set_tick_params(color=GH_TEXT_MUTED, labelcolor=GH_TEXT_MUTED)
        cbar.set_label("Job Postings", color=GH_TEXT_MUTED, fontsize=11)

        ax.set_title(
            f"IT Job Postings Heatmap - {n_regions} German States",
            pad=16, color=GH_TEXT, fontsize=15, fontweight="bold"
        )
        for spine in ax.spines.values():
            spine.set_edgecolor(GH_BORDER)

        plt.tight_layout()
        path = self.plots_dir / "01_job_distribution.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG, bbox_inches="tight")
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def plot_country_comparison(self, df: pd.DataFrame) -> Optional[Path]:
        index_cols = [c for c in df.columns if c.endswith("_index_de100")]
        if df.empty or not index_cols:
            logger.warning("No country comparison data - skipping")
            return None

        col = index_cols[0]
        plot_df = df[["country_code", col]].dropna().copy()
        plot_df = plot_df[plot_df["country_code"] != "EU27_2020"]
        plot_df["country"] = plot_df["country_code"].map(COUNTRY_LABELS).fillna(plot_df["country_code"])
        plot_df = plot_df.sort_values(col, ascending=True)
        colors = [COUNTRY_COLORS.get(c, GH_BLUE) for c in plot_df["country_code"]]

        fig, ax = plt.subplots(figsize=(13, 7))
        _gh(fig, ax)

        bars = ax.barh(plot_df["country"], plot_df[col], color=colors, alpha=0.85, height=0.6)
        ax.axvline(x=100, color=GH_TEXT_MUTED, linestyle="--", linewidth=1.2, label="Germany = 100")

        for bar, val in zip(bars, plot_df[col]):
            ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                   f"{val:.0f}", va="center", fontsize=9, color=GH_TEXT)

        ax.set_title("IT Specialist Index vs. Germany  (Germany = 100)", pad=12)
        ax.set_xlabel("Index")
        ax.tick_params(axis="y", colors=GH_TEXT)
        legend = ax.legend(facecolor=GH_BG_CARD, edgecolor=GH_BORDER, labelcolor=GH_TEXT)

        plt.tight_layout()
        path = self.plots_dir / "02_country_comparison.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG)
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def plot_timeseries(self, df: pd.DataFrame) -> Optional[Path]:
        if df.empty:
            logger.warning("No time series data - skipping")
            return None

        dataset = df["dataset"].unique()[0]
        plot_df = df[df["dataset"] == dataset].copy()

        fig, ax = plt.subplots(figsize=(15, 7))
        _gh(fig, ax)

        for country in sorted(plot_df["country_code"].unique()):
            if country == "EU27_2020":
                continue
            sub = plot_df[plot_df["country_code"] == country].sort_values("year")
            lw = 2.5 if country == "DE" else 1.4
            color = COUNTRY_COLORS.get(country, GH_BLUE)
            ax.plot(sub["year"], sub["value"], marker="o", markersize=4,
                   label=COUNTRY_LABELS.get(country, country), linewidth=lw, color=color)

        ax.set_title(f"IT Employment Trend by Country - {dataset}", pad=12)
        ax.set_xlabel("Year")
        ax.set_ylabel("Value")
        ax.tick_params(colors=GH_TEXT)
        legend = ax.legend(title="Country", fontsize=8,
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
        if forecasts_df.empty:
            logger.warning("No forecast data - skipping")
            return None

        dataset = forecasts_df["dataset"].unique()[0]
        plot_df = forecasts_df[forecasts_df["dataset"] == dataset].copy()

        fig, ax = plt.subplots(figsize=(15, 7))
        _gh(fig, ax)

        for country in sorted(plot_df["country_code"].unique()):
            if country == "EU27_2020":
                continue
            sub = plot_df[plot_df["country_code"] == country].sort_values("year")
            hist = sub[sub["type"] == "historical"]
            fcast = sub[sub["type"] == "forecast"]
            lw = 2.5 if country == "DE" else 1.4
            color = COUNTRY_COLORS.get(country, GH_BLUE)
            line, = ax.plot(hist["year"], hist["fitted"], linewidth=lw,
                           color=color, label=COUNTRY_LABELS.get(country, country))
            ax.plot(fcast["year"], fcast["fitted"], linewidth=lw,
                   linestyle="--", color=color, alpha=0.7)

        forecast_start = plot_df[plot_df["type"] == "historical"]["year"].max()
        ax.axvline(x=forecast_start, color=GH_TEXT_MUTED, linestyle=":",
                  linewidth=1, label="Forecast start")

        ax.set_title(f"IT Labor Market Forecast to 2029 - {dataset}", pad=12)
        ax.set_xlabel("Year")
        ax.set_ylabel("Value")
        ax.tick_params(colors=GH_TEXT)
        legend = ax.legend(title="-- = forecast", fontsize=8,
                          bbox_to_anchor=(1.01, 1), loc="upper left",
                          facecolor=GH_BG_CARD, edgecolor=GH_BORDER, labelcolor=GH_TEXT)
        legend.get_title().set_color(GH_TEXT_MUTED)

        plt.tight_layout()
        path = self.plots_dir / "04_forecast.png"
        plt.savefig(path, dpi=150, facecolor=GH_BG)
        plt.close()
        logger.info("Plot saved: %s", path)
        return path

    def generate_all(self, job_features, country_comparison, timeseries, forecasts):
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

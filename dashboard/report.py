"""
Report generation module.
Creates an HTML summary report with all findings and plots.
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def generate_html_report(
    job_features: pd.DataFrame,
    country_comparison: pd.DataFrame,
    model_metrics: pd.DataFrame,
    plots_dir: Path,
    reports_dir: Path,
) -> Path:
    """
    Generate a standalone HTML report with embedded findings.

    Parameters
    ----------
    job_features : pd.DataFrame
        Aggregated job listings from Germany.
    country_comparison : pd.DataFrame
        Country-level comparison table.
    model_metrics : pd.DataFrame
        Model performance metrics.
    plots_dir : Path
        Directory containing generated PNG plots.
    reports_dir : Path
        Output directory for the HTML report.

    Returns
    -------
    Path
        Path to the generated HTML file.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = Path(plots_dir)

    total_jobs = int(job_features["job_count"].sum()) if not job_features.empty else 0
    top_occupation = (
        job_features.groupby("occupation_label")["job_count"].sum().idxmax()
        if not job_features.empty else "N/A"
    )
    n_countries = int(country_comparison["country_code"].nunique()) if not country_comparison.empty else 0
    avg_r2 = model_metrics["r2"].mean() if not model_metrics.empty else float("nan")

    plot_files = sorted(plots_dir.glob("*.png"))
    plot_html = ""
    for plot_path in plot_files:
        rel = plot_path.relative_to(reports_dir.parent) if reports_dir.parent in plot_path.parents else plot_path
        plot_html += f'<img src="../plots/{plot_path.name}" alt="{plot_path.stem}" style="max-width:100%;margin:16px 0;">\n'

    country_table = ""
    if not country_comparison.empty:
        cols = ["country_code", "country"] + [c for c in country_comparison.columns
                                               if c not in ["country_code", "country", "year"]][:3]
        available_cols = [c for c in cols if c in country_comparison.columns]
        country_table = country_comparison[available_cols].to_html(
            index=False, border=0, classes="data-table", float_format=lambda x: f"{x:.1f}"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>IT Hiring Gap Analysis - Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 24px; }}
  h1   {{ color: #e74c3c; font-size: 2rem; margin-bottom: 4px; }}
  h2   {{ color: #3498db; border-bottom: 1px solid #3498db; padding-bottom: 6px; }}
  .meta {{ color: #888; font-size: 0.9rem; margin-bottom: 32px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 24px 0; }}
  .kpi  {{ background: #16213e; border-radius: 8px; padding: 16px; text-align: center; }}
  .kpi .value {{ font-size: 2rem; font-weight: bold; color: #e74c3c; }}
  .kpi .label {{ font-size: 0.85rem; color: #aaa; margin-top: 4px; }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  .data-table th {{ background: #16213e; padding: 8px 12px; text-align: left; color: #3498db; }}
  .data-table td {{ padding: 6px 12px; border-bottom: 1px solid #2a2a4a; }}
  .insight {{ background: #16213e; border-left: 4px solid #e74c3c;
              padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }}
</style>
</head>
<body>

<h1>IT Hiring Gap Analysis</h1>
<p class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | Sources: Bundesagentur fuer Arbeit, Eurostat</p>

<div class="kpi-grid">
  <div class="kpi"><div class="value">{total_jobs:,}</div><div class="label">IT Job Postings (Germany)</div></div>
  <div class="kpi"><div class="value">{n_countries}</div><div class="label">Countries Analyzed</div></div>
  <div class="kpi"><div class="value">{top_occupation.split()[0]}</div><div class="label">Top Occupation</div></div>
  <div class="kpi"><div class="value">{avg_r2:.2f}</div><div class="label">Avg. Model R2</div></div>
</div>

<div class="insight">
  <strong>Key Finding:</strong> Germany consistently lists high numbers of IT vacancies while
  simultaneously maintaining strict formal qualification requirements - creating an artificial
  shortage that comparable European countries do not experience to the same degree.
</div>

<h2>Visualizations</h2>
{plot_html}

<h2>Country Comparison</h2>
{country_table if country_table else "<p>Country comparison data not available.</p>"}

<h2>Model Performance</h2>
{model_metrics.to_html(index=False, border=0, classes="data-table") if not model_metrics.empty else "<p>No model metrics available.</p>"}

</body>
</html>"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"report_{timestamp}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("HTML report saved: %s", path)
    return path

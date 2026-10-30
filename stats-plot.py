
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ============================================================
# Configuration
# ============================================================

RESULTS_DIR = Path("statistical_results")
PLOT_DIR = RESULTS_DIR / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = [2023, 2024, 2025, 2026]
TOP_N_THEMES = 20
TOP_N_DOMAINS = 20


# ============================================================
# Load statistical results
# ============================================================

theme_results = pd.read_csv(
    RESULTS_DIR / "thematic_cluster_trends.csv"
)
domain_results = pd.read_csv(
    RESULTS_DIR / "medical_domain_trends_min10.csv"
)
theme_prev = pd.read_csv(
    RESULTS_DIR / "thematic_cluster_prevalence_by_year.csv"
)
domain_prev = pd.read_csv(
    RESULTS_DIR / "medical_domain_prevalence_by_year.csv"
)


# ============================================================
# Export helper
# ============================================================

def export_figure(fig, filename):
    """Save interactive HTML and static PNG, PDF and SVG."""
    fig.write_html(PLOT_DIR / f"{filename}.html")

    for fmt in ["png", "pdf", "svg"]:
        try:
            fig.write_image(
                PLOT_DIR / f"{filename}.{fmt}",
                scale=2 if fmt == "png" else 1,
            )
        except Exception as exc:
            print(
                f"Could not export {filename}.{fmt}: {exc}\n"
                "HTML is available; check the Kaleido installation "
                "for static export."
            )


def polish(fig, height=None):
    fig.update_layout(
        template="plotly_white",
        font=dict(size=12),
        margin=dict(l=30, r=35, t=75, b=45),
        height=height,
        legend_title_text="",
    )
    return fig


# ============================================================
# 1. Trend lines: FDR-significant thematic clusters
# ============================================================

significant_themes = theme_results.loc[
    theme_results["p_fdr"] < 0.05, "label"
].tolist()

if significant_themes:
    plot_data = theme_prev[
        theme_prev["label"].isin(significant_themes)
    ].copy()

    plot_data["year"] = plot_data["year"].astype(str)

    fig = px.line(
        plot_data,
        x="year",
        y="percentage",
        color="label",
        markers=True,
        category_orders={"year": [str(y) for y in YEARS]},
        hover_data={
            "n_with_label": True,
            "n_contributions": True,
            "percentage": ":.1f",
        },
        title="Temporal trends in FDR-significant thematic clusters",
        labels={
            "year": "Year",
            "percentage": "Contributions assigned to cluster (%)",
            "label": "Thematic cluster",
            "n_with_label": "Contributions assigned",
            "n_contributions": "All contributions that year",
        },
    )

    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    fig.update_yaxes(rangemode="tozero")
    polish(fig, height=520)
    export_figure(fig, "01_significant_theme_trends")


# ============================================================
# 2. Forest plot: all thematic clusters
# ============================================================

def forest_plot(results, title, filename):
    if results.empty:
        print(f"No results available for {title}")
        return

    data = results.sort_values("OR_per_year").copy()
    data["status"] = data["p_fdr"].apply(
        lambda p: "FDR-significant" if p < 0.05
        else "Not FDR-significant"
    )

    fig = go.Figure()

    for status in ["Not FDR-significant", "FDR-significant"]:
        d = data[data["status"] == status]
        if d.empty:
            continue

        fig.add_trace(
            go.Scatter(
                x=d["OR_per_year"],
                y=d["label"],
                mode="markers",
                name=status,
                error_x=dict(
                    type="data",
                    symmetric=False,
                    array=d["CI95_high"] - d["OR_per_year"],
                    arrayminus=d["OR_per_year"] - d["CI95_low"],
                    visible=True,
                    thickness=1.4,
                    width=3,
                ),
                customdata=d[
                    ["CI95_low", "CI95_high", "p_value", "p_fdr"]
                ],
                hovertemplate=(
                    "%{y}<br>"
                    "OR per year: %{x:.2f}<br>"
                    "95% CI: %{customdata[0]:.2f}–"
                    "%{customdata[1]:.2f}<br>"
                    "p-value: %{customdata[2]:.4g}<br>"
                    "FDR-adjusted p: %{customdata[3]:.4g}"
                    "<extra></extra>"
                ),
            )
        )

    fig.add_vline(
        x=1,
        line_dash="dash",
        line_width=1,
        annotation_text="OR = 1",
        annotation_position="top",
    )

    fig.update_xaxes(type="log", title="Odds ratio per year (log scale)")
    fig.update_yaxes(title="", automargin=True)

    polish(fig, height=max(500, 28 * len(data) + 140))
    fig.update_layout(title=title)
    export_figure(fig, filename)


forest_plot(
    theme_results,
    "Temporal trends by thematic cluster",
    "02_forest_plot_themes",
)

forest_plot(
    domain_results,
    "Temporal trends by medical domain (≥10 assignments)",
    "03_forest_plot_medical_domains",
)


# ============================================================
# 3. Heatmap: prevalence by year
# ============================================================

def prevalence_heatmap(prevalence, title, filename, top_n=20):
    data = prevalence.copy()

    # Select the most frequently assigned labels overall.
    totals = (
        data.groupby("label")["n_with_label"]
        .sum()
        .sort_values(ascending=False)
    )
    selected = totals.head(top_n).index
    data = data[data["label"].isin(selected)]

    matrix = data.pivot(
        index="label",
        columns="year",
        values="percentage",
    ).reindex(columns=YEARS)

    # Order rows by overall frequency.
    order = totals.loc[matrix.index].sort_values().index
    matrix = matrix.loc[order]

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=[str(y) for y in matrix.columns],
            y=matrix.index,
            colorbar=dict(title="Contributions (%)"),
            hovertemplate=(
                "Label: %{y}<br>"
                "Year: %{x}<br>"
                "Share: %{z:.1f}%<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Year",
        yaxis_title="",
        yaxis=dict(automargin=True),
    )

    polish(fig, height=max(550, 28 * len(matrix) + 150))
    export_figure(fig, filename)


prevalence_heatmap(
    theme_prev,
    "Thematic cluster prevalence by year",
    "04_heatmap_themes",
    top_n=TOP_N_THEMES,
)

prevalence_heatmap(
    domain_prev,
    "TOP 20 Medical domain prevalence by year",
    "05_heatmap_medical_domains",
    top_n=TOP_N_DOMAINS,
)


print(f"Plots saved in: {PLOT_DIR.resolve()}")

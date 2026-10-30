from pathlib import Path

import pandas as pd
import plotly.express as px


# ============================================================
# 1. Settings
# ============================================================

INPUT_FILE = Path("../../ohdsi_evidence_master.xlsx")
SHEET_NAME = "ohdsi_evidence_master"
OUTPUT_DIR = Path("../../statistical_results/plots")

TOP_N_THEMES = 25
TOP_N_MEDICAL_DOMAINS = 25

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. Load and prepare data
# ============================================================

df = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)

required_columns = [
    "Year",
    "Category",
    "ThematicCluster",
    "Medical Domain",
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing columns: {missing_columns}\n"
        f"Available columns: {list(df.columns)}"
    )

# Convert years to numeric values and restrict the data to the analysis period
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
df = df[df["Year"].isin([2023, 2024, 2025, 2026])].copy()
df["Year"] = df["Year"].astype(int)

years = [2023, 2024, 2025, 2026]
year_labels = [str(y) for y in years]

# Label missing categories for the analyses below
for col in ["Category", "ThematicCluster"]:
    df[col] = df[col].fillna("Not specified").astype(str).str.strip()
    df.loc[df[col] == "", col] = "Not specified"

# Create consistent year labels
df["YearLabel"] = df["Year"].astype(str)


# ============================================================
# Helper function: export charts
# ============================================================

def export_figure(fig, filename):
    """Save a Plotly figure as HTML and, if possible,
    additionally as PNG, SVG, and PDF."""
    fig.write_html(OUTPUT_DIR / f"{filename}.html")

    try:
        fig.write_image(OUTPUT_DIR / f"{filename}.png", scale=2)
        fig.write_image(OUTPUT_DIR / f"{filename}.svg")
        fig.write_image(OUTPUT_DIR / f"{filename}.pdf")
    except Exception as exc:
        print(
            f"Static export for {filename} was not possible. "
            f"HTML was saved. Details: {exc}"
        )


# ============================================================
# 3. Chart 1: Number of contributions per year
# ============================================================

contributions_per_year = (
    df.groupby("Year")
    .size()
    .reindex(years, fill_value=0)
    .rename("Contributions")
    .reset_index()
)

contributions_per_year["Year"] = (
    contributions_per_year["Year"].astype(str)
)

fig1 = px.bar(
    contributions_per_year,
    x="Year",
    y="Contributions",
    text="Contributions",
    category_orders={"Year": year_labels},
    title="Number of OHDSI Contributions per Year",
    labels={
        "Year": "Year",
        "Contributions": "Number of contributions",
    },
)

fig1.update_traces(textposition="outside")
fig1.update_layout(template="plotly_white")

fig1.show()
export_figure(fig1, "06_contributions_per_year")


# ============================================================
# 4. Chart 2: Category distribution by year
# ============================================================

category_counts = (
    df.groupby(["YearLabel", "Category"])
    .size()
    .reset_index(name="Count")
)

category_counts["Share"] = (
    category_counts["Count"]
    / category_counts["YearLabel"].map(
        df["YearLabel"].value_counts()
    )
    * 100
)

category_counts.to_csv(
    OUTPUT_DIR / "category_counts_by_year.csv",
    index=False,
    encoding="utf-8-sig",
)

fig2 = px.bar(
    category_counts,
    x="YearLabel",
    y="Share",
    color="Category",
    barmode="stack",
    category_orders={"YearLabel": year_labels},
    title="Distribution of OHDSI Contribution Categories by Year",
    labels={
        "YearLabel": "Year",
        "Share": "Share of contributions (%)",
        "Category": "Category",
    },
)

fig2.update_layout(
    template="plotly_white",
    yaxis_ticksuffix="%",
)

fig2.show()
export_figure(fig2, "07_category_distribution")


# ============================================================
# 5. Chart 3: Thematic cluster heatmap by year
# ============================================================

# A contribution can contain multiple thematic clusters,
# separated by semicolons. Each cluster is counted separately.
theme_source = df[["Year", "YearLabel", "Themencluster"]].copy()

theme_source["Themencluster"] = (
    theme_source["Themencluster"]
    .fillna("")
    .astype(str)
    .str.split(";")
)

theme_long = theme_source.explode("Themencluster")

theme_long["Themencluster"] = (
    theme_long["Themencluster"]
    .fillna("")
    .astype(str)
    .str.strip()
)

# Exclude empty entries and "Not specified"
theme_long = theme_long[
    (theme_long["Themencluster"] != "")
    & (
        theme_long["Themencluster"].str.casefold()
        != "not specified"
    )
].copy()

if theme_long.empty:
    raise ValueError(
        "No thematic cluster entries found after cleaning."
    )

# Count the occurrences of each thematic cluster by year
theme_counts = (
    theme_long.groupby(["YearLabel", "Themencluster"])
    .size()
    .reset_index(name="Mentions")
)

theme_counts.to_csv(
    OUTPUT_DIR / "themencluster_counts_by_year.csv",
    index=False,
    encoding="utf-8-sig",
)

# Calculate the total number of mentions for each thematic cluster
theme_total_counts = (
    theme_long["Themencluster"]
    .value_counts()
    .rename_axis("Themencluster")
    .reset_index(name="Mentions")
)

theme_total_counts.to_csv(
    OUTPUT_DIR / "themencluster_counts.csv",
    index=False,
    encoding="utf-8-sig",
)

# Identify the most frequent thematic clusters across all years
top_theme_names = (
    theme_total_counts
    .head(TOP_N_THEMES)["Themencluster"]
    .tolist()
)

# Matrix: thematic clusters in rows and years in columns
theme_year_matrix = (
    theme_counts[
        theme_counts["Themencluster"].isin(top_theme_names)
    ]
    .pivot(
        index="Themencluster",
        columns="YearLabel",
        values="Mentions",
    )
    .reindex(
        index=top_theme_names,
        columns=year_labels,
    )
    .fillna(0)
)

# Share of contributions in each year that mention the respective thematic cluster.
# Multiple assignments are possible; therefore, the percentages do not
# necessarily add up to 100%.
year_totals = (
    df.groupby("YearLabel")
    .size()
    .reindex(year_labels, fill_value=0)
)

theme_year_percentages = theme_year_matrix.astype(float)

for year in year_labels:
    denominator = year_totals.loc[year]

    if denominator > 0:
        theme_year_percentages[year] = (
            theme_year_percentages[year]
            / denominator
            * 100
        )
    else:
        theme_year_percentages[year] = 0

theme_year_percentages.to_csv(
    OUTPUT_DIR / "themencluster_percentage_by_year.csv",
    encoding="utf-8-sig",
)

# Create heatmap
fig3 = px.imshow(
    theme_year_percentages,
    x=year_labels,
    y=theme_year_percentages.index,
    aspect="auto",
    text_auto=".1f",
    color_continuous_scale="Blues",
    title=f"Thematic Clusters by Year",
    labels={
        "x": "Year",
        "y": "Thematic cluster",
        "color": "Share of contributions (%)",
    },
)

fig3.update_layout(
    template="plotly_white",
    coloraxis_colorbar_ticksuffix="%",
)

fig3.show()
export_figure(fig3, "08_themencluster_by_year")


# ============================================================
# 6. Medical domains: split and clean entries
# ============================================================

# A contribution can contain multiple medical domains,
# separated by semicolons. Each domain is counted separately.
medical_source = df[["Year", "YearLabel", "Medical Domain"]].copy()

medical_source["Medical Domain"] = (
    medical_source["Medical Domain"]
    .fillna("")
    .astype(str)
)

medical_source["Medical Domain"] = (
    medical_source["Medical Domain"]
    .str.split(";")
)

medical_long = medical_source.explode("Medical Domain")

medical_long["Medical Domain"] = (
    medical_long["Medical Domain"]
    .fillna("")
    .astype(str)
    .str.strip()
)

# Exclude empty entries and "Not specified"
medical_long = medical_long[
    (medical_long["Medical Domain"] != "")
    & (
        medical_long["Medical Domain"].str.casefold()
        != "not specified"
    )
].copy()

if medical_long.empty:
    raise ValueError(
        "No medical domain entries found after cleaning."
    )

# Optional: Count duplicate mentions of the same domain within a
# contribution and year only once. Since the Excel file does not require
# a unique contribution ID, counting here is based on the
# available rows.


# ============================================================
# 7. Chart 4: Development of medical domains by year
# ============================================================

medical_domain_counts = (
    medical_long["Medical Domain"]
    .value_counts()
    .rename_axis("Medical Domain")
    .reset_index(name="Mentions")
)

medical_domain_counts.to_csv(
    OUTPUT_DIR / "medical_domain_counts.csv",
    index=False,
    encoding="utf-8-sig",
)

top_medical_domains = medical_domain_counts.head(
    TOP_N_MEDICAL_DOMAINS
).copy()


medical_domain_year_counts = (
    medical_long.groupby(["YearLabel", "Medical Domain"])
    .size()
    .reset_index(name="Mentions")
)

medical_domain_year_counts.to_csv(
    OUTPUT_DIR / "medical_domain_counts_by_year.csv",
    index=False,
    encoding="utf-8-sig",
)

# Select the top domains by total number of mentions
top_domain_names = top_medical_domains[
    "Medical Domain"
].tolist()

domain_year_matrix = (
    medical_domain_year_counts[
        medical_domain_year_counts["Medical Domain"].isin(
            top_domain_names
        )
    ]
    .pivot(
        index="Medical Domain",
        columns="YearLabel",
        values="Mentions",
    )
    .reindex(
        index=top_domain_names,
        columns=year_labels,
    )
    .fillna(0)
)

# Share of contributions in a given year that mention the respective domain.
# Multiple assignments are possible; therefore, the percentages across
# domains do not necessarily add up to 100%.
year_totals = (
    df.groupby("YearLabel")
    .size()
    .reindex(year_labels, fill_value=0)
)

domain_year_percentages = domain_year_matrix.copy().astype(float)

for year in year_labels:
    denominator = year_totals.loc[year]

    if denominator > 0:
        domain_year_percentages[year] = (
            domain_year_percentages[year] / denominator * 100
        )
    else:
        domain_year_percentages[year] = 0

domain_year_percentages.to_csv(
    OUTPUT_DIR / "medical_domain_percentage_by_year.csv",
    encoding="utf-8-sig",
)

fig5 = px.imshow(
    domain_year_percentages,
    x=year_labels,
    y=domain_year_percentages.index,
    aspect="auto",
    text_auto=".1f",
    color_continuous_scale="Blues",
    title=f"Top {TOP_N_MEDICAL_DOMAINS} Medical Domains by Year",
    labels={
        "x": "Year",
        "y": "Medical Domain",
        "color": "Share of contributions (%)",
    },
)

fig5.update_layout(
    template="plotly_white",
    coloraxis_colorbar_ticksuffix="%",
)

fig5.show()
export_figure(fig5, "09_medical_domains_by_year")


# ============================================================
# 8. Summary
# ============================================================

print("\nAnalysis completed.")
print(f"Number of contributions analyzed: {len(df)}")
print(f"Years: {', '.join(year_labels)}")
print(
    "Medical domain mentions after excluding "
    f"'Not specified': {len(medical_long)}"
)
print(f"Results saved to: {OUTPUT_DIR.resolve()}")
print(
    "\nNote: Kaleido may be required for PNG, SVG, and PDF exports. "
    "Install it using: pip install kaleido"
)

from pathlib import Path
from math import exp

import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

# --------------------------------------------------
# Configuration
# --------------------------------------------------

INPUT_FILE = Path("ohdsi_evidence_master.xlsx")
OUTPUT_DIR = Path("statistical_results")
OUTPUT_DIR.mkdir(exist_ok=True)

YEAR_COL = "Year"
THEME_COL = "Themencluster"
DOMAIN_COL = "Medical Domain"

MIN_DOMAIN_COUNT = 10
YEARS = [2023, 2024, 2025, 2026]


# --------------------------------------------------
# Load and prepare data
# --------------------------------------------------

df = pd.read_excel(INPUT_FILE)

required_cols = [YEAR_COL, THEME_COL, DOMAIN_COL]
missing = [col for col in required_cols if col not in df.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}")

df[YEAR_COL] = pd.to_numeric(df[YEAR_COL], errors="coerce")
df = df[df[YEAR_COL].isin(YEARS)].copy()

print("Number of contributions per year:")
print(df[YEAR_COL].value_counts().sort_index())


# --------------------------------------------------
# Expand semicolon-separated labels
# --------------------------------------------------

def split_labels(value):
    if pd.isna(value):
        return []
    return [
        label.strip()
        for label in str(value).split(";")
        if label.strip()
    ]


def create_indicator_matrix(data, column, prefix):
    """
    Create one binary indicator per distinct label.
    Each contribution can have multiple labels.
    """
    labels = data[column].apply(split_labels)

    all_labels = sorted({
        label
        for row in labels
        for label in row
        if label.lower() != "not specified"
    })

    indicators = pd.DataFrame(
        {
            f"{prefix}{label}": labels.apply(
                lambda row: int(label in row)
            )
            for label in all_labels
        },
        index=data.index,
    )

    return indicators


theme_indicators = create_indicator_matrix(
    df, THEME_COL, "theme__"
)

domain_indicators = create_indicator_matrix(
    df, DOMAIN_COL, "domain__"
)


# --------------------------------------------------
# Descriptive prevalence by year
# --------------------------------------------------

def prevalence_by_year(data, indicators):
    rows = []

    for year in YEARS:
        yearly = data[data[YEAR_COL] == year]
        n_year = len(yearly)

        for col in indicators.columns:
            count = int(indicators.loc[yearly.index, col].sum())

            rows.append({
                "year": year,
                "label": col.split("__", 1)[1],
                "n_contributions": n_year,
                "n_with_label": count,
                "percentage": (
                    100 * count / n_year if n_year else float("nan")
                ),
            })

    return pd.DataFrame(rows)


theme_prevalence = prevalence_by_year(df, theme_indicators)
domain_prevalence = prevalence_by_year(df, domain_indicators)

theme_prevalence.to_csv(
    OUTPUT_DIR / "thematic_cluster_prevalence_by_year.csv",
    index=False,
)
domain_prevalence.to_csv(
    OUTPUT_DIR / "medical_domain_prevalence_by_year.csv",
    index=False,
)


# --------------------------------------------------
# Logistic regression and odds ratios
# --------------------------------------------------

def analyse_trends(data, indicators, min_count=1):
    results = []

    for col in indicators.columns:
        y = indicators[col].astype(int)

        # Exclude labels with too few occurrences overall.
        if int(y.sum()) < min_count:
            continue

        # Logistic regression requires both outcome classes.
        if y.nunique() < 2:
            continue

        model_data = pd.DataFrame({
            "year": data[YEAR_COL].astype(float),
            "outcome": y,
        }).dropna()

        X = sm.add_constant(model_data["year"])

        try:
            model = sm.Logit(
                model_data["outcome"], X
            ).fit(disp=False)

            beta = model.params["year"]
            ci_low, ci_high = model.conf_int().loc["year"]

            results.append({
                "label": col.split("__", 1)[1],
                "n_contributions": len(model_data),
                "n_with_label": int(model_data["outcome"].sum()),
                "OR_per_year": exp(beta),
                "CI95_low": exp(ci_low),
                "CI95_high": exp(ci_high),
                "p_value": model.pvalues["year"],
            })

        except Exception as exc:
            print(f"Could not fit model for {col}: {exc}")

    results = pd.DataFrame(results)

    if results.empty:
        return results

    results["p_fdr"] = multipletests(
        results["p_value"],
        method="fdr_bh",
    )[1]

    results["significant_fdr_0.05"] = results["p_fdr"] < 0.05

    return results.sort_values("p_fdr")


# --------------------------------------------------
# Run analyses
# --------------------------------------------------

theme_results = analyse_trends(
    df,
    theme_indicators,
    min_count=1,
)

domain_results = analyse_trends(
    df,
    domain_indicators,
    min_count=MIN_DOMAIN_COUNT,
)

theme_results.to_csv(
    OUTPUT_DIR / "thematic_cluster_trends.csv",
    index=False,
)

domain_results.to_csv(
    OUTPUT_DIR / "medical_domain_trends_min10.csv",
    index=False,
)


# --------------------------------------------------
# Report significant trends
# --------------------------------------------------

print("\nFDR-significant thematic trends:")
if not theme_results.empty:
    print(
        theme_results[
            theme_results["significant_fdr_0.05"]
        ].to_string(index=False)
    )

print("\nFDR-significant medical-domain trends:")
if not domain_results.empty:
    print(
        domain_results[
            domain_results["significant_fdr_0.05"]
        ].to_string(index=False)
    )

print(f"\nResults saved in: {OUTPUT_DIR.resolve()}")

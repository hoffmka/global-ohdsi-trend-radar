# OHDSI Global Symposium Trend Radar (2023–2026)

## Overview

This repository presents a **Trend Radar of the OHDSI Global Symposium and Collaborator Showcase contributions from 2023 to 2026**. It explores how research topics and medical domains represented in the OHDSI community have evolved over time.

The Trend Radar combines descriptive visualizations with statistical trend analyses to identify recurring themes, emerging areas of interest, and changes in the distribution of contributions across symposium years.

The analysis is intended to provide an exploratory overview of community activity. It does not measure the quality or impact of individual contributions, nor does it represent the entire OHDSI community beyond the contributions included in the dataset.

## Dataset

The evidence list was compiled from publicly available OHDSI materials, including contributions to the OHDSI Global Symposium and the Collaborator Showcase. Contributions from 2023 to 2026 were consolidated into the master dataset, `ohdsi_evidence_master.xlsx`, which served as the basis for the subsequent analysis.

The dataset contains 601 contributions:
| Year | Number of Contribution |
| :--- |  ---: |
| 2023 |  161 |
| 2024 |  136 |
| 2025 |  142 |
| 2026 |  162 |
| **Total** |  **601** |

Each contribution is described using metadata including its year, original category, contribution number, title, thematic cluster, and medical domain.

The thematic and medical-domain assignments were derived from contribution titles. A second researcher independently reviewed the assignments, and differences were discussed until consensus was reached.

## Analytical Approach

### Descriptive Analysis

The descriptive analysis examines the distribution of contributions across symposium years, thematic clusters, and medical domains. It provides an overview of the topics represented in the dataset and how their prevalence changes over time.

### Statistical Trend Analysis

To assess whether the representation of individual themes and medical domains changed over time, separate logistic regression models were fitted for each label.

**Outcome:** Whether a contribution was assigned to a particular theme or medical domain.

**Predictor:** Calendar year, modelled as a continuous variable from 2023 to 2026.

**Effect measure:** Odds ratio (OR) per one-year increase, with a Wald 95% confidence interval.

**Multiple testing:** Benjamini–Hochberg false discovery rate (FDR) correction, applied separately to thematic clusters and medical domains.

**Medical domains:** Statistical trend models were restricted to domains assigned to at least 10 contributions overall.

An odds ratio above 1 indicates increasing odds of a label being assigned in later years; an odds ratio below 1 indicates decreasing odds. Statistical significance was assessed using FDR-adjusted p-values.

Annual prevalence percentages use the total number of contributions in each year as the denominator. As contributions may be assigned to multiple themes or medical domains, percentages across labels do not necessarily sum to 100%.

## Key Findings

Three thematic clusters showed statistically significant upward trends after FDR correction:

**AI, LLMs & Natural Language Processing:** OR per year = 1.70 (95% CI 1.36–2.12; FDR-adjusted p = 3.54 × 10⁻⁵). Prevalence increased from 5.0% in 2023 to 23.5% in 2026.

**Federated Analytics & Network Studies:** OR per year = 1.60 (95% CI 1.15–2.23; FDR-adjusted p = 0.0282). Prevalence increased from 1.9% in 2023 to 9.3% in 2026.

**Data Standardization & OMOP CDM:** OR per year = 1.24 (95% CI 1.07–1.43; FDR-adjusted p = 0.0258). Prevalence increased from 28.6% in 2023 to 45.1% in 2026, after reaching approximately 47.9% in 2025.

No medical-domain trend reached statistical significance after FDR correction among domains with at least 10 assignments.

These findings describe changes in the **relative representation of topics among the analysed contributions**. They should not be interpreted as evidence of causality or as definitive measures of broader community-wide research activity.

## Statistical Visualizations

The statistical analysis produces five main Plotly visualizations. Interactive HTML versions are provided, with static PNG, PDF, and SVG exports attempted where the required export dependencies are available.

### 1. Forest Plot of Thematic Trends

A forest plot showing the estimated odds ratios and 95% confidence intervals for thematic clusters. It includes both statistically significant and non-significant trends, allowing readers to compare the estimated direction and magnitude of changes across themes.

The vertical reference at OR = 1 represents no temporal association in the model.

**Figure 1. Temporal Trends by thematic cluster**

![Temporal Trends by thematic cluster](statistical_results/plots/02_forest_plot_themes.png)



### 3. Forest Plot of Medical-Domain Trends

A forest plot of odds ratios and 95% confidence intervals for medical domains with at least 10 assignments overall. It provides a comparative overview of estimated temporal trends across medical areas. None of these trends remained statistically significant after FDR correction.

**Figure 3. Temporal Trends by medcial-domain cluster**
![Temporal Trends by thematic cluster](statistical_results/plots/03_forest_plot_medical_domains.png)

### 4. Heatmap of Thematic Prevalence

A heatmap showing annual prevalence percentages for the represented thematic clusters. It supports rapid visual comparison of which themes are consistently represented, increase, decrease, or fluctuate across the four symposium years.

**Figure 4. Thematic cluster prevalence by year**

![Thematic cluster prevalence by year](statistical_results/plots/04_heatmap_themes.png)


### 5. Heatmap of Medical-Domain Prevalence

A heatmap showing annual prevalence percentages for the 25 most frequently represented medical domains. It illustrates the distribution and temporal variation of the medical areas represented in the contributions.

**Figure 5. Medical domain prevalence by year**

![Medical domain prevalence by year](statistical_results/plots/05_heatmap_medical_domains.png)

The exact file extensions depend on the generated outputs. The interactive versions use HTML; static exports are generated where supported.

## Repository contents

The repository brings together the contribution-level dataset, analysis scripts, statistical result tables, and visualizations.

Key statistical result tables include:

- `thematic_cluster_trends.csv` — Regression estimates and statistical results for thematic clusters.

- `medical_domain_trends_min10.csv` — Regression estimates for medical domains meeting the minimum assignment threshold.

- `thematic_cluster_prevalence_by_year.csv` — Annual prevalence of thematic clusters.

- `medical_domain_prevalence_by_year.csv` — Annual prevalence of medical domains.

Statistical plots are stored in `statistical_results/plots/`. The original contribution data are maintained in `ohdsi_evidence_master.xlsx`.

## Reproducibility

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows, activate it with:

```powershell
.venv\Scripts\activate
```

Install the required dependencies from requirements.txt:

```bash
pip install -r requirements.txt
```

Run the analysis:

```bash
python stats.py
python stats-plot.py
```
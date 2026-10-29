"""Preparedness score, following Final_Formula.ipynb from
https://github.com/miroeramaa/VolcanoReadiness (Preparedness folder).

preparedness = weighted geometric mean of 3 components, each clipped to [epsilon, 1]:
  1. hazard maps   log(10 * n_hazard_maps / ln(100)), capped at 1, missing -> 0
                   (1 map ~ 0.78, 2 or more maps = 1)
  2. health        healthcare per capita, min-max rescaled to 0-1
  3. HDI           Human Development Index, min-max rescaled to 0-1
weights = 0.33, 0.33, 0.34
"""
import math

import numpy as np
import pandas as pd

EPSILON = 0.1                  # smallest value a component can have
WEIGHTS = (0.33, 0.33, 0.34)   # hazard maps, health, HDI

# Column used for "healthcare per capita".
# The notebook uses a placeholder (5.0 for every volcano, so health counts
# the same for all). Set HEALTH_COLUMN = None to reproduce the notebook exactly.
HEALTH_COLUMN = "fac_per_10k_ring"     # health facilities per 10,000 people (10-50 km ring)
NOTEBOOK_HEALTH_PLACEHOLDER = 5.0


def min_max_rescale(minimum, maximum, value):
    if maximum == minimum:
        return value
    return (value - minimum) / (maximum - minimum)


def weighted_gmean(components: np.ndarray, weights) -> np.ndarray:
    """Weighted geometric mean of each row (same result as scipy.stats.gmean with weights)."""
    w = np.asarray(weights, dtype=float)
    return np.exp((np.log(components) * w).sum(axis=1) / w.sum())


def preparedness_index(df: pd.DataFrame, epsilon=EPSILON, weights=WEIGHTS) -> np.ndarray:
    # 1. hazard maps (log of 0 maps is -inf; the clip below turns it into epsilon)
    with np.errstate(divide="ignore"):
        hazard_maps = np.log(10.0 * df["n_hazard_maps"] / math.log(100.0)).clip(upper=1).fillna(0)

    # 2. healthcare per capita
    health = df["n_health_per_capita"]
    health = min_max_rescale(health.min(), health.max(), health).fillna(0)

    # 3. HDI (as in the notebook: missing values filled with the mean raw HDI)
    hdi = min_max_rescale(df["HDI"].min(), df["HDI"].max(), df["HDI"]).fillna(df["HDI"].mean())

    comps = np.column_stack([hazard_maps, health, hdi]).clip(epsilon, 1)
    return weighted_gmean(comps, weights)


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Give every volcano a preparedness score between 0 (unprepared) and 1 (fully prepared).

    Input:  volcano_preparedness_data.csv (volcano_number, volcano_name, lat, lon,
            n_hazard_maps, HDI and the health column above)
    Output: gvp_volcano_number, name, lat, lon, preparedness_score
    """
    df = df.copy()
    df["n_health_per_capita"] = (df[HEALTH_COLUMN] if HEALTH_COLUMN
                                 else NOTEBOOK_HEALTH_PLACEHOLDER)
    df["preparedness_score"] = preparedness_index(df)

    df = df.rename(columns={"volcano_number": "gvp_volcano_number", "volcano_name": "name"})
    return df[["gvp_volcano_number", "name", "lat", "lon", "preparedness_score"]]
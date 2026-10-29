import pandas as pd
import numpy as np

MIDPOINT = None   # population that scores 0.5; None = use the median
STEEPNESS = 2
def score(df: pd.DataFrame) -> pd.DataFrame:
    """Give every volcano a population score between 0 (nobody) and 1 (most people).

    Input:  the population file (must have name, lat, lon, population_10km)
    Output: name, lat, lon, population_score
    """
    df = df.copy()

    # TODO: replace with your real population calculation
    df = df.copy()
    log_pop = np.log10(df["population_10km"] + 1)  # +1 so 0 people works
    mid = np.log10(MIDPOINT if MIDPOINT else df["population_10km"].median())
    df["population_score"] = 1 / (1 + np.exp(-STEEPNESS * (log_pop - mid)))
    return df[["name", "lat", "lon", "population_score"]]

    return df[["name", "lat", "lon", "population_score"]]
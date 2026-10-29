"""Hazard score:  hazard = sqrt(magnitude * recency) * certainty

magnitude  how big it can erupt     (0.6 * vei_max + 0.4 * vei_last_eruption) / 8
recency    how active it is now     1 - log10(1 + years since last eruption) / log10(1 + HORIZON_YEARS)
certainty  how reliable the record  confirmed 1.0, uncertain 0.7, no data 0.5
"""
import numpy as np
import pandas as pd

CURRENT_YEAR = 2026
HORIZON_YEARS = 12_000          # roughly the Holocene; older or unknown -> lowest recency
DEFAULT_VEI = 2                 # used when VEI is unknown
WEIGHT_VEI_MAX = 0.6            # rest goes to vei_last_eruption
FLOOR = 0.1                     # smallest value magnitude and recency can have
CERTAINTY = {"confirmed": 1.0, "uncertain": 0.7}
CERTAINTY_NO_DATA = 0.5


def magnitude(df: pd.DataFrame) -> pd.Series:
    vei_max = df["vei_max"].fillna(DEFAULT_VEI)
    vei_last = df["vei_last_eruption"].fillna(vei_max)
    m = (WEIGHT_VEI_MAX * vei_max + (1 - WEIGHT_VEI_MAX) * vei_last) / 8
    return m.clip(FLOOR, 1)


def recency(df: pd.DataFrame) -> pd.Series:
    years_ago = (CURRENT_YEAR - df["last_eruption"]).clip(lower=0).fillna(HORIZON_YEARS)
    r = 1 - np.log10(1 + years_ago) / np.log10(1 + HORIZON_YEARS)
    return r.clip(FLOOR, 1)


def certainty(df: pd.DataFrame) -> pd.Series:
    return df["eruption_certainty"].map(CERTAINTY).fillna(CERTAINTY_NO_DATA)


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hazard_score"] = np.sqrt(magnitude(df) * recency(df)) * certainty(df)
    return df[["name", "lat", "lon", "hazard_score"]]
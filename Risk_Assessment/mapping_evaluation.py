import pandas as pd


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Turn the mapping percentage (0-100) into a score between 0 and 1.

    Input:  name, lat, lon, mapping_percentage
    Output: name, lat, lon, mapping_score
    """
    df = df.copy()
    df["mapping_score"] = df["mapping_percentage"] / 100
    return df[["name", "lat", "lon", "mapping_score"]]
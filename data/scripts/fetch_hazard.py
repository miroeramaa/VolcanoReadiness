"""Build data/processed/hazard.csv for the 264 volcanoes within 10 deg of the equator.

Uses only local files (no internet):
  data/processed/volcanoes_10deg_equator.csv  volcano list (GVP number, name, lat, lon,
                                              type, evidence, last known eruption, ...)
  data/raw/Eruption_Volcanoes.csv             GVP eruption records (year, VEI)

Output: data/processed/hazard.csv
        (an existing hazard.csv is first saved as hazard_old.csv, once)

Columns kept compatible with Risk_Assessment/hazard_evaluation.py:
  name, lat, lon, gvp_volcano_number, last_eruption, vei_max,
  vei_last_eruption, eruption_certainty

last_eruption = latest of (start year, end year, GVP "Last Known Eruption"), so
ongoing eruptions count as recent. last_eruption_start = start year of the latest
eruption record; vei_last_eruption belongs to that eruption.

Note: Eruption_Volcanoes.csv only holds confirmed eruptions, so eruption_certainty
is "confirmed" when a volcano has records and empty when it has none. The GVP
evidence label (activity_evidence) is kept so you can see why it is empty.
"""
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent
VOLCANO_LIST = DATA / "processed" / "volcanoes_10deg_equator.csv"
ERUPTIONS = DATA / "raw" / "Eruption_Volcanoes.csv"
OUTPUT = DATA / "processed" / "hazard.csv"
BACKUP = DATA / "processed" / "hazard_old.csv"

CURRENT_YEAR = 2026
RECENT_SINCE = 1900          # "recent" eruptions = started in or after this year


def parse_gvp_year(text) -> float:
    """'1887 CE' -> 1887, '8300 BCE' -> -8300, 'Unknown' -> NaN."""
    m = re.match(r"\s*(\d+)\s*(BCE|CE)", str(text))
    if not m:
        return np.nan
    year = int(m.group(1))
    return -year if m.group(2) == "BCE" else year


def summarise(eruptions: pd.DataFrame) -> pd.DataFrame:
    """One row of eruption statistics per volcano."""
    out = []
    for number, g in eruptions.groupby("volcano_number"):
        g = g.sort_values("start_year")
        last = g.iloc[-1]
        out.append({
            "volcano_number": number,
            "last_eruption_start": last["start_year"],
            "last_activity_in_records": max(g["start_year"].max(), g["end_year"].max(skipna=True)
                                            if g["end_year"].notna().any() else -np.inf),
            "vei_max": g["vei"].max(),
            "vei_last_eruption": last["vei"],
            "eruption_certainty": "confirmed",
            "vei_mean": g["vei"].mean(),
            "n_eruptions": len(g),
            "n_eruptions_with_vei": int(g["vei"].notna().sum()),
            f"n_eruptions_since_{RECENT_SINCE}": int((g["start_year"] >= RECENT_SINCE).sum()),
            "n_eruptions_vei3_plus": int((g["vei"] >= 3).sum()),
            "first_eruption": g["start_year"].min(),
        })
    return pd.DataFrame(out)


def main():
    volcanoes = pd.read_csv(VOLCANO_LIST)
    eruptions = pd.read_csv(ERUPTIONS).rename(columns={
        "Volcano Number": "volcano_number", "VEI": "vei", "Start Year": "start_year", "End Year": "end_year",
    })
    eruptions = eruptions[eruptions["volcano_number"].isin(volcanoes["volcano_number"])]
    stats = summarise(eruptions)

    df = volcanoes.merge(stats, on="volcano_number", how="left")
    df["gvp_last_known_eruption"] = df["Last Known Eruption"].map(parse_gvp_year)
    # Ongoing eruptions started years ago (e.g. Nyiragongo 2002) but are active now,
    # so last_eruption = latest of start year, end year and GVP's last known year.
    df["last_eruption"] = df[["last_activity_in_records", "gvp_last_known_eruption"]].max(axis=1)
    df["years_since_last_eruption"] = CURRENT_YEAR - df["last_eruption"]
    for c in ["n_eruptions", "n_eruptions_with_vei", f"n_eruptions_since_{RECENT_SINCE}",
              "n_eruptions_vei3_plus"]:
        df[c] = df[c].fillna(0).astype(int)          # no records = 0 eruptions
    df = df.rename(columns={
        "volcano_name": "name", "volcano_number": "gvp_volcano_number", "Country": "country",
        "Primary Volcano Type": "volcano_type", "Activity Evidence": "activity_evidence",
        "Elevation (m)": "elevation_m", "Tectonic Setting": "tectonic_setting",
    })

    for c in ["last_eruption", "last_eruption_start", "first_eruption", "vei_max", "vei_last_eruption",
              "n_eruptions_with_vei", f"n_eruptions_since_{RECENT_SINCE}",
              "n_eruptions_vei3_plus", "years_since_last_eruption", "gvp_last_known_eruption"]:
        df[c] = df[c].astype("Int64")
    df["vei_mean"] = df["vei_mean"].round(2)

    cols = ["name", "gvp_volcano_number", "country", "lat", "lon",
            "last_eruption", "vei_max", "vei_last_eruption", "eruption_certainty",
            "years_since_last_eruption", "last_eruption_start", "vei_mean", "n_eruptions", "n_eruptions_with_vei",
            f"n_eruptions_since_{RECENT_SINCE}", "n_eruptions_vei3_plus", "first_eruption",
            "gvp_last_known_eruption", "activity_evidence", "volcano_type",
            "elevation_m", "tectonic_setting"]
    df = df[cols]

    if OUTPUT.exists() and not BACKUP.exists():
        shutil.copy(OUTPUT, BACKUP)
        print(f"Saved previous hazard file as {BACKUP.name}")
    df.to_csv(OUTPUT, index=False)

    print(f"{len(df)} volcanoes -> {OUTPUT.relative_to(DATA.parent)}")
    print(f"{(df['n_eruptions'] > 0).sum()} have eruption records, "
          f"{(df['n_eruptions'] == 0).sum()} have none")
    print("Missing values per column:")
    print(df.isna().sum()[lambda s: s > 0].to_string() or "  none")


if __name__ == "__main__":
    main()

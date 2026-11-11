from pathlib import Path

import pandas as pd
import numpy as np
import geopandas as gpd
import fiona

from pyproj import CRS, Transformer
from shapely.geometry import Point
from shapely.ops import transform, unary_union


MIDPOINT = None   # population that scores 0.5; None = use the median
STEEPNESS = 2
RADIUS = 10       # km



# Kontur population dataset, downloaded by hand and put in the data folder:
# https://geodata-eu-central-1-kontur-public.s3.eu-central-1.amazonaws.com/kontur_datasets/kontur_population_20231101.gpkg.gz
DATA = Path(__file__).resolve().parent.parent / "data"
KONTUR_FILE = DATA / "kontur_population_20231101.gpkg"


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Give every volcano a population score between 0 and 1.

    Input:  name, lat, lon
    Output: name, lat, lon, population_score
    """
    cache = DATA / "kontur_10km_population_scores.csv"
    if cache.exists():
        cached = pd.read_csv(cache)
        if len(cached) == len(df) and (cached["name"].values == df["name"].values).all():
            print("Using saved population scores from", cache.name)
            return cached[["name", "lat", "lon", "population_score"]]

    if not KONTUR_FILE.exists():
        raise FileNotFoundError(
            f"Kontur population file not found at {KONTUR_FILE}\n"
            "Download it (see the link at the top of this file), unzip it, "
            "and put the .gpkg file in the data folder."
        )

    df = df.copy().reset_index(drop=True)

    # Get Kontur CRS and population column
    with fiona.open(KONTUR_FILE) as file:
        source_crs = CRS.from_user_input(file.crs_wkt or file.crs)
    pop_column = "population"

    results = []

    # Calculate population within 10 km of each volcano
    for _, row in df.iterrows():

        lat = float(row["lat"])
        lon = float(row["lon"])

        print("Processing", row["name"])

        local_crs = CRS.from_proj4(
            f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
            "+datum=WGS84 +units=m +no_defs"
        )

        circle = Point(0, 0).buffer(RADIUS * 1000, quad_segs=96)

        to_wgs = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True)
        circle_wgs = transform(to_wgs.transform, circle)

        to_source = Transformer.from_crs("EPSG:4326", source_crs, always_xy=True)
        bounds = to_source.transform_bounds(*circle_wgs.bounds, densify_pts=21)

        cells = gpd.read_file(KONTUR_FILE, bbox=bounds).to_crs(local_crs)

        cells = cells[
            cells.geometry.notna()
            & ~cells.geometry.is_empty
            & cells.geometry.intersects(circle)
        ].copy()

        population = pd.to_numeric(cells[pop_column], errors="coerce")
        inside = cells.geometry.intersection(circle)

        fraction = (
            inside.area / cells.geometry.area.replace(0, np.nan)
        ).clip(0, 1)

        valid = population.notna() & np.isfinite(population) & (population >= 0)

        # No people in the circle counts as 0, not "missing"
        total = (population * fraction).where(valid).sum()

        coverage = (
            100 * unary_union(list(inside)).area / circle.area
            if not cells.empty else 0
        )

        area = circle.area / 1_000_000

        results.append({
            "population_on_10km": total,
            "mean_density_people_per_km2": total / area,
            "hexagons_intersecting": len(cells),
            "hexagons_with_valid_population": int(valid.sum()),
            "hexagons_with_invalid_population": int((~valid).sum()),
            "kontur_geometry_coverage_pct": coverage
        })

    # Add calculated population to the original DataFrame
    population_data = pd.DataFrame(results)
    df = pd.concat([df, population_data], axis=1)

    # Calculate population scores (+1 so a median of 0 people doesn't break log10)
    log_pop = np.log10(df["population_on_10km"] + 1)
    mid = np.log10((MIDPOINT if MIDPOINT else df["population_on_10km"].median()) + 1)

    df["population_score"] = 1 / (
        1 + np.exp(-STEEPNESS * (log_pop - mid))
    )

    # Save detailed results
    df.to_csv(DATA / "kontur_10km_population_scores.csv", index=False)

    # Return only the required columns
    return df[["name", "lat", "lon", "population_score"]]
"""for testing purposes
# Load volcano data
volcanoes = pd.read_csv(
    DATA_FOLDER / "GVP_Volcano_List_Holocene.csv"
)

# Rename columns
volcanoes = volcanoes.rename(columns={
    "Volcano Name": "name",
    "Latitude": "lat",
    "Longitude": "lon"
})

# Run population scoring
results = score(volcanoes)

# Display results
print(results) """
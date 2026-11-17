"""Find the OpenStreetMap version of every GVP volcano within 10 degrees of the equator.

How it matches (strongest first):
  1. wikidata   - the OSM feature has a wikidata tag pointing to the Wikidata item
                  that carries this GVP volcano number. Exact, no guessing.
  2. name       - an OSM volcano within MAX_KM whose name is similar enough.
  3. distance   - no name match, but an OSM volcano is very close (< CLOSE_KM).
  4. none       - nothing found; the nearest OSM volcano is still listed so you
                  can check it by hand.

Put this file in "Fetching OSM volcanoes" and run it. Output:
  data/processed/gvp_osm_matches.csv
"""

import json
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------- settings
LAT_LIMIT = 10      # degrees north/south of the equator
MAX_KM = 10         # search radius for name matches
CLOSE_KM = 2        # accept without a name match if this close
MIN_SIMILARITY = 0.6  # 0-1, how alike the names must be

DATA = Path(__file__).resolve().parent.parent / "data"
GVP_FILE = DATA / "raw" / "GVP_Volcano_List_Holocene.csv"
OSM_CACHE = DATA / "raw" / "osm_volcanoes_raw.json"         # saved so reruns are instant
WIKIDATA_CACHE = DATA / "raw" / "wikidata_gvp_ids.json"
OUTPUT = DATA / "processed" / "gvp_osm_matches.csv"

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "VolcanoReadiness-student-project/1.0"}


# ---------------------------------------------------------------- download
def fetch_osm_volcanoes() -> pd.DataFrame:
    """All OSM features tagged natural=volcano in the equator band (one request)."""
    if OSM_CACHE.exists():
        print("Using saved OSM data from", OSM_CACHE.name)
        elements = json.loads(OSM_CACHE.read_text(encoding="utf-8"))
    else:
        s, n = -LAT_LIMIT - 1, LAT_LIMIT + 1   # 1 degree margin for edge cases
        query = f"""
        [out:json][timeout:300];
        (
          node["natural"="volcano"]({s},-180,{n},180);
          way["natural"="volcano"]({s},-180,{n},180);
          relation["natural"="volcano"]({s},-180,{n},180);
        );
        out center tags;
        """
        elements = None
        for url in OVERPASS_SERVERS:
            try:
                print("Downloading OSM volcanoes from", url, "...")
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=360)
                r.raise_for_status()
                elements = r.json()["elements"]
                break
            except Exception as e:
                print("  failed:", e)
                time.sleep(5)
        if elements is None:
            raise RuntimeError("Could not reach any Overpass server. Try again later.")
        OSM_CACHE.write_text(json.dumps(elements), encoding="utf-8")

    rows = []
    for el in elements:
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        names = [tags.get(k) for k in ("name", "name:en", "alt_name", "old_name", "official_name")]
        rows.append({
            "osm_type": el["type"],
            "osm_id": el["id"],
            "osm_name": tags.get("name", ""),
            "osm_all_names": [n for n in names if n],
            "osm_lat": lat,
            "osm_lon": lon,
            "osm_wikidata": tags.get("wikidata", ""),
        })
    df = pd.DataFrame(rows)
    print(len(df), "OSM volcanoes in the equator band")
    return df


def fetch_wikidata_gvp_ids() -> dict:
    """Map GVP volcano number -> Wikidata item (property P1886, Smithsonian volcano ID)."""
    if WIKIDATA_CACHE.exists():
        return {int(k): v for k, v in json.loads(WIKIDATA_CACHE.read_text()).items()}
    query = "SELECT ?item ?gvp WHERE { ?item wdt:P1886 ?gvp . }"
    try:
        print("Downloading GVP numbers from Wikidata ...")
        r = requests.get("https://query.wikidata.org/sparql",
                         params={"query": query, "format": "json"},
                         headers=HEADERS, timeout=120)
        r.raise_for_status()
    except Exception as e:
        print("  Wikidata failed, matching by name/distance only:", e)
        return {}
    mapping = {}
    for b in r.json()["results"]["bindings"]:
        try:
            mapping[int(b["gvp"]["value"])] = b["item"]["value"].rsplit("/", 1)[-1]
        except ValueError:
            pass
    WIKIDATA_CACHE.write_text(json.dumps(mapping))
    return mapping


# ---------------------------------------------------------------- matching
PREFIXES = ["gunung", "mount", "mt", "volcan", "volcano", "nevado del", "nevado de",
            "nevado", "cerro", "kawah", "ol doinyo", "pico", "monte", "ili", "bukit"]


def clean(name: str) -> str:
    """'Ruiz, Nevado del' and 'Volcán Nevado del Ruiz' both become 'ruiz'."""
    if not isinstance(name, str):
        return ""
    if "," in name:                                   # GVP style: "Ruiz, Nevado del"
        a, b = name.split(",", 1)
        name = f"{b} {a}"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = name.replace("-", " ").replace(".", " ")
    words = name.split()
    changed = True
    while changed and len(words) > 1:                 # strip leading words like "gunung"
        changed = False
        for p in PREFIXES:
            pw = p.split()
            if words[:len(pw)] == pw and len(words) > len(pw):
                words = words[len(pw):]
                changed = True
    return " ".join(w for w in words if w not in ("volcano", "volcanic", "field", "crater"))


def similarity(a: str, b: str) -> float:
    a, b = clean(a), clean(b)
    if not a or not b:
        return 0.0
    wa, wb = set(a.split()), set(b.split())
    if wa <= wb or wb <= wa:          # all words of one name appear in the other
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def distance_km(lat, lon, lats, lons):
    lat, lon, lats, lons = map(np.radians, (lat, lon, lats, lons))
    h = np.sin((lats - lat) / 2) ** 2 + np.cos(lat) * np.cos(lats) * np.sin((lons - lon) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(h))


def match(gvp: pd.DataFrame, osm: pd.DataFrame, wikidata: dict) -> pd.DataFrame:
    by_qid = {q: i for i, q in osm["osm_wikidata"].items() if q}
    results = []

    for _, v in gvp.iterrows():
        d = distance_km(v.lat, v.lon, osm["osm_lat"].values, osm["osm_lon"].values)
        sims = np.array([max((similarity(v.volcano_name, n) for n in names), default=0)
                         for names in osm["osm_all_names"]])

        idx, method = None, "none"
        qid = wikidata.get(int(v.volcano_number))
        if qid and qid in by_qid:                                    # 1. wikidata
            idx, method = by_qid[qid], "wikidata"
        else:
            ok = (d <= MAX_KM) & (sims >= MIN_SIMILARITY)
            if ok.any():                                             # 2. name
                cand = np.where(ok)[0]
                idx = cand[np.argmax(sims[cand] - d[cand] / 100)]    # best name, then closest
                method = "name"
            elif len(d) and d.min() <= CLOSE_KM:                     # 3. distance
                idx, method = int(d.argmin()), "distance"

        row = {"volcano_number": v.volcano_number, "volcano_name": v.volcano_name,
               "gvp_lat": v.lat, "gvp_lon": v.lon, "match_method": method,
               "wikidata": qid or ""}
        if idx is not None:
            o = osm.iloc[idx]
            row.update(osm_type=o.osm_type, osm_id=o.osm_id, osm_name=o.osm_name,
                       osm_lat=o.osm_lat, osm_lon=o.osm_lon,
                       distance_km=round(float(d[idx]), 2),
                       name_similarity=round(float(sims[idx]), 2))
        else:
            n = int(d.argmin()) if len(d) else None
            if n is not None:
                row.update(nearest_osm_name=osm.iloc[n].osm_name,
                           nearest_osm_id=osm.iloc[n].osm_id,
                           nearest_km=round(float(d[n]), 2))
        results.append(row)

    out = pd.DataFrame(results)
    # Flag OSM features that got matched to more than one GVP volcano
    if "osm_id" in out:
        dup = out["osm_id"].notna() & out.duplicated(["osm_type", "osm_id"], keep=False)
        out["check"] = np.where(dup, "same OSM feature used twice", "")
    return out


# ---------------------------------------------------------------- run
if __name__ == "__main__":
    gvp = pd.read_csv(GVP_FILE, encoding_errors="ignore")
    gvp = gvp[gvp["Latitude"].between(-LAT_LIMIT, LAT_LIMIT)].rename(columns={
        "Volcano Number": "volcano_number", "Volcano Name": "volcano_name",
        "Latitude": "lat", "Longitude": "lon"})
    print(len(gvp), "GVP volcanoes within", LAT_LIMIT, "degrees of the equator")

    osm = fetch_osm_volcanoes()
    wikidata = fetch_wikidata_gvp_ids()

    result = match(gvp.reset_index(drop=True), osm, wikidata)
    result.to_csv(OUTPUT, index=False)

    print("\nResults saved to", OUTPUT)
    print(result["match_method"].value_counts().to_string())
    if "check" in result:
        print((result["check"] != "").sum(), "rows flagged for checking")

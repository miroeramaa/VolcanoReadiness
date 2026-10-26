import pandas as pd
import zipfile

GVP_WFS = "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows"
GVP_LAYER = "GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes"

def find_volcano_smithsonian(name: str) -> pd.DataFrame:
    """Case-insensitive partial-name search of the GVP Holocene list."""
    import requests
 
    safe = name.replace("'", "''")
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": GVP_LAYER,
        "outputFormat": "application/json",
        "propertyName": "Volcano_Number,Volcano_Name,Country,Latitude,Longitude,"
                        "Last_Eruption_Year",
        "CQL_FILTER": f"Volcano_Name ILIKE '%{safe}%'",
    }
    r = requests.get(GVP_WFS, params=params, timeout=60)
    r.raise_for_status()
    rows = [f["properties"] for f in r.json().get("features", [])]
    return pd.DataFrame(rows)

GVP_LAYER = "GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes"

def find_volcano_local(name: str, path: str) -> pd.DataFrame:
    """Same search against a GVP list exported from volcano.si.edu."""
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
    else:
        # GVP's Excel export has a title row above the header
        raw = pd.read_excel(path, header=None)
        hdr = raw.index[raw.apply(
            lambda r: r.astype(str).str.contains("Volcano Number").any(), axis=1)][0]
        df = pd.read_excel(path, header=hdr)
    df = df.rename(columns={c: _norm(c) for c in df.columns})
    df = df.rename(columns={"volcanonumber": "Volcano_Number",
                            "volcanoname": "Volcano_Name",
                            "country": "Country",
                            "latitude": "Latitude",
                            "longitude": "Longitude",
                            "lasteruptionyear": "Last_Eruption_Year"})
    hit = df["Volcano_Name"].astype(str).str.contains(name, case=False, regex=False)
    keep = [c for c in ["Volcano_Number", "Volcano_Name", "Country", "Latitude",
                        "Longitude", "Last_Eruption_Year"] if c in df.columns]
    return df.loc[hit, keep].reset_index(drop=True)
 


def load_gvmid_stations(zip_path: str, verbose: bool = True) -> pd.DataFrame:
    """Read every sheet of every spreadsheet in the GVMID package into one
    table of stations: method, lat, lon, end_date (if present), source."""
    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            low = member.lower()
            if not low.endswith((".xls", ".xlsx", ".csv")):
                continue
            data = zf.read(member)
            if low.endswith(".csv"):
                sheets = {"csv": pd.read_csv(io.BytesIO(data))}
            else:
                sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
            for sheet, df in sheets.items():
                if df.empty:
                    continue
                lat = _find_col(df.columns, [r"lat"])
                lon = _find_col(df.columns, [r"lon"])
                if lat is None or lon is None:
                    if verbose:
                        print(f"  skipped {member}/{sheet}: no lat/lon columns "
                              f"(columns: {list(df.columns)[:12]})")
                    continue
                end = _find_col(df.columns,
                                [r"etime$", r"enddate", r"end$", r"removed",
                                 r"uninstall", r"endtime"])
                out = pd.DataFrame({
                    "method": _method_from(f"{member} {sheet}"),
                    "lat": pd.to_numeric(df[lat], errors="coerce"),
                    "lon": pd.to_numeric(df[lon], errors="coerce"),
                    "end_date": df[end] if end is not None else pd.NA,
                    "source": f"{member} / {sheet}",
                })
                frames.append(out.dropna(subset=["lat", "lon"]))
                if verbose:
                    print(f"  read {len(out):>6} rows from {member} / {sheet} "
                          f"(lat={lat}, lon={lon}, end={end})")
    if not frames:
        raise ValueError("No station tables with latitude/longitude found in "
                         f"{zip_path}. Check the column names printed above.")
    return pd.concat(frames, ignore_index=True)
 

"""Load a Smithsonian GVP volcano list export (.xls) into a pandas DataFrame.

GVP's ".xls" downloads are often XML Spreadsheet 2003 files with an .xls
extension, which pd.read_excel can't open, so this checks what the file
really is. It also skips the title row(s) above the real header.

    from load_gvp import load_gvp
    df = load_gvp("GVP_Volcano_List_Holocene_202610190409.xls")
"""
import re
import xml.etree.ElementTree as ET

import pandas as pd

SS = "{urn:schemas-microsoft-com:office:spreadsheet}"  # SpreadsheetML namespace


def _clean_xml(text):
    """Fix what GVP's export gets wrong: bare '&' that isn't an entity, and
    control characters that aren't allowed in XML."""
    text = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]", "", text)


def _parse_xml(path):
    raw = open(path, "rb").read()
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        pass
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)  # encoding now handled
    try:
        return ET.fromstring(_clean_xml(text))
    except ET.ParseError:
        try:  # last resort: lxml's forgiving parser (pip install lxml)
            from lxml import etree
            parser = etree.XMLParser(recover=True, huge_tree=True)
            return ET.fromstring(etree.tostring(etree.fromstring(raw, parser)))
        except ImportError:
            raise


def _read_spreadsheetml(path):
    rows = []
    for row in _parse_xml(path).iter(f"{SS}Row"):
        cells = []
        for cell in row.findall(f"{SS}Cell"):
            idx = cell.get(f"{SS}Index")  # skipped empty cells
            if idx:
                cells += [None] * (int(idx) - 1 - len(cells))
            data = cell.find(f"{SS}Data")
            cells.append(data.text if data is not None else None)
        rows.append(cells)
    return pd.DataFrame(rows)


def _read_raw(path):
    with open(path, "rb") as f:
        head = f.read(512).lstrip().lower()
    if head.startswith(b"<?xml") and b"spreadsheet" in head + open(path, "rb").read(4096).lower():
        return _read_spreadsheetml(path)
    if head.startswith((b"<html", b"<table", b"<!doctype")):
        return pd.read_html(path, header=None)[0]
    return pd.read_excel(path, header=None)  # genuine .xls (needs xlrd) / .xlsx


def load_gvp(path):
    raw = _read_raw(path)
    # the real header is the row containing "Volcano Number"
    is_header = raw.apply(lambda r: r.astype(str).str.strip().eq("Volcano Number").any(), axis=1)
    if not is_header.any():
        raise ValueError(f"No 'Volcano Number' header row found in {path}")
    h = is_header.idxmax()
    df = raw.iloc[h + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[h]]
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    for col in ["Volcano Number", "Latitude", "Longitude", "Elevation (m)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


if __name__ == "__main__":
    import sys

    df = load_gvp(sys.argv[1] if len(sys.argv) > 1
                  else "GVP_Volcano_List_Holocene_202610190409.xls")
    print(df.shape)
    print(df.columns.tolist())
    print(df.head())

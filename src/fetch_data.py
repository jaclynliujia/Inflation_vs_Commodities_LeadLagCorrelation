"""
fetch_data.py
-------------
Pull monthly CPI (CPIAUCSL) and PPI: All Commodities (PPIACO) from FRED's
public CSV endpoint and write tidy CSVs to data/.

No API key required.

Usage
-----
    python src/fetch_data.py            # default 1975-01-01 to today
    python src/fetch_data.py 1990 2020  # custom start/end years

Outputs
-------
    data/cpi_monthly.csv               (date, cpi)
    data/ppi_commodities_monthly.csv   (date, ppi)
    data/merged_yoy.csv                (date, cpi_yoy, ppi_yoy)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}&coed={end}"

SERIES = {
    "cpi": "CPIAUCSL",     # CPI for All Urban Consumers: All Items, Index 1982-84=100
    "ppi": "PPIACO",       # Producer Price Index by Commodity: All Commodities, Index 1982=100
}


def fetch_series(series_id: str, start: str, end: str) -> pd.Series:
    """Download a FRED series as a pandas Series indexed by date."""
    url = FRED_CSV.format(series=series_id, start=start, end=end)
    df = pd.read_csv(url)
    df.columns = [c.lower() for c in df.columns]
    # Older FRED CSVs use 'date'; newer use 'observation_date'
    date_col = "observation_date" if "observation_date" in df.columns else "date"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    value_col = [c for c in df.columns if c != date_col][0]
    s = pd.to_numeric(df[value_col], errors="coerce").dropna()
    s.name = series_id
    return s


def yoy(s: pd.Series) -> pd.Series:
    """Year-over-year percentage change (12-month lag for monthly data)."""
    return (s / s.shift(12) - 1.0) * 100.0


def main(start_year: int = 1975, end_year: int | None = None) -> None:
    end_year = end_year or datetime.today().year
    start = f"{start_year - 1}-01-01"  # one extra year for the YoY lag
    end = f"{end_year}-12-31"

    out = Path(__file__).resolve().parents[1] / "data"
    out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {SERIES['cpi']} ({start} to {end})...")
    cpi = fetch_series(SERIES["cpi"], start, end)
    cpi.to_frame("cpi").to_csv(out / "cpi_monthly.csv")

    print(f"Fetching {SERIES['ppi']} ({start} to {end})...")
    ppi = fetch_series(SERIES["ppi"], start, end)
    ppi.to_frame("ppi").to_csv(out / "ppi_commodities_monthly.csv")

    merged = pd.concat([yoy(cpi).rename("cpi_yoy"), yoy(ppi).rename("ppi_yoy")], axis=1)
    merged = merged.dropna()
    merged = merged[merged.index.year >= start_year]
    merged.to_csv(out / "merged_yoy.csv")

    print(f"Wrote {len(merged)} monthly rows to {out / 'merged_yoy.csv'}")
    print(f"Range: {merged.index.min().date()}  ->  {merged.index.max().date()}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 0:
        main()
    elif len(args) == 1:
        main(int(args[0]))
    else:
        main(int(args[0]), int(args[1]))

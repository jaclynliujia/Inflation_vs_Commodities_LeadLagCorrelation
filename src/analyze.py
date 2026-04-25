"""
analyze.py
----------
Compute correlation statistics between US headline CPI YoY % change and the
PPI: All Commodities YoY % change.

Reads from one of two sources, in this order of preference:
    1. data/merged_yoy.csv          (live monthly data — produced by fetch_data.py)
    2. data/annual_snapshot.csv     (bundled annual snapshot — works out of the box)

Outputs CSVs and a printed summary to stdout. The numbers reported in the README
are reproduced by running this script.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def load_data() -> tuple[pd.DataFrame, str]:
    """Return a DataFrame with columns [cpi_yoy, ppi_yoy] and a frequency tag."""
    monthly_path = DATA / "merged_yoy.csv"
    if monthly_path.exists():
        df = pd.read_csv(monthly_path, parse_dates=[0], index_col=0).dropna()
        df.index.name = "date"
        return df, "monthly"

    snap = pd.read_csv(DATA / "annual_snapshot.csv")
    snap["cpi_yoy"] = (snap["cpi_index"] / snap["cpi_index"].shift(1) - 1) * 100
    snap["ppi_yoy"] = (
        snap["ppi_commodities_index"] / snap["ppi_commodities_index"].shift(1) - 1
    ) * 100
    snap = snap.dropna().set_index("year")[["cpi_yoy", "ppi_yoy"]]
    return snap, "annual"


def lead_lag_corr(x: pd.Series, y: pd.Series, max_lag: int = 12) -> pd.DataFrame:
    """Pearson correlation of x with y shifted by k periods (k positive => y lags x)."""
    rows = []
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            a, b = x.iloc[k:], y.iloc[: len(y) - k] if k > 0 else y
        else:
            a, b = x.iloc[: len(x) + k], y.iloc[-k:]
        a, b = a.align(b, join="inner")[0], a.align(b, join="inner")[1]  # noqa
        # simpler: use shift
        pair = pd.concat([x, y.shift(k)], axis=1).dropna()
        if len(pair) < 10:
            continue
        r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
        rows.append({"lag_periods": k, "n": len(pair), "pearson_r": r, "p_value": p})
    return pd.DataFrame(rows)


def regime_table(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Correlations broken out by decade (or 5y bucket if too few obs)."""
    s = df.copy()
    s["decade"] = (s.index.year if freq == "monthly" else s.index) // 10 * 10
    rows = []
    for d, g in s.groupby("decade"):
        if len(g) < 5:
            continue
        r, p = stats.pearsonr(g["cpi_yoy"], g["ppi_yoy"])
        rows.append(
            {
                "decade": f"{int(d)}s",
                "n": len(g),
                "pearson_r": round(r, 3),
                "p_value": round(p, 4),
                "cpi_yoy_mean": round(g["cpi_yoy"].mean(), 2),
                "ppi_yoy_mean": round(g["ppi_yoy"].mean(), 2),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    df, freq = load_data()
    print(f"Loaded {len(df)} {freq} observations "
          f"({df.index.min()} to {df.index.max()})\n")

    # ---- 1. Full-sample correlations -------------------------------------
    pearson_r, pearson_p = stats.pearsonr(df["cpi_yoy"], df["ppi_yoy"])
    spearman_r, spearman_p = stats.spearmanr(df["cpi_yoy"], df["ppi_yoy"])

    full_sample = pd.DataFrame(
        {
            "metric": ["pearson_r", "pearson_p", "spearman_r", "spearman_p", "n"],
            "value": [
                round(pearson_r, 4),
                f"{pearson_p:.2e}",
                round(spearman_r, 4),
                f"{spearman_p:.2e}",
                len(df),
            ],
        }
    )
    full_sample.to_csv(OUT / "correlations_full_sample.csv", index=False)
    print("Full-sample correlation")
    print("-----------------------")
    print(full_sample.to_string(index=False))
    print()

    # ---- 2. Linear regression -------------------------------------------
    slope, intercept, r, p, se = stats.linregress(df["ppi_yoy"], df["cpi_yoy"])
    reg = pd.DataFrame(
        {
            "metric": ["slope_beta", "intercept_alpha", "r_squared", "p_value", "std_err"],
            "value": [round(slope, 4), round(intercept, 4), round(r ** 2, 4),
                      f"{p:.2e}", round(se, 4)],
        }
    )
    reg.to_csv(OUT / "regression_cpi_on_ppi.csv", index=False)
    print(f"OLS regression: cpi_yoy = {intercept:.3f} + {slope:.3f} * ppi_yoy")
    print(f"  R^2 = {r ** 2:.4f}     p = {p:.2e}     n = {len(df)}\n")

    # ---- 3. Decade-by-decade --------------------------------------------
    decades = regime_table(df, freq)
    decades.to_csv(OUT / "correlations_by_decade.csv", index=False)
    print("Correlation by decade")
    print("---------------------")
    print(decades.to_string(index=False))
    print()

    # ---- 4. Lead/lag (monthly only) -------------------------------------
    if freq == "monthly":
        ll = lead_lag_corr(df["cpi_yoy"], df["ppi_yoy"], max_lag=12)
        ll.to_csv(OUT / "lead_lag_correlations.csv", index=False)
        peak = ll.iloc[ll["pearson_r"].abs().idxmax()]
        print("Lead-lag analysis (PPI shifted by k months relative to CPI)")
        print("-----------------------------------------------------------")
        print(ll.to_string(index=False))
        print(f"\nPeak |r| at lag = {int(peak['lag_periods'])} months "
              f"(r = {peak['pearson_r']:.3f})")
        if peak["lag_periods"] < 0:
            print("=> Commodity prices LEAD CPI (typical interpretation).")
        elif peak["lag_periods"] > 0:
            print("=> CPI leads commodity prices.")
        else:
            print("=> Contemporaneous relationship dominates.")
        print()

    # ---- 5. Rolling correlation (monthly only) --------------------------
    if freq == "monthly":
        roll = df["cpi_yoy"].rolling(60).corr(df["ppi_yoy"]).dropna()
        roll.to_frame("rolling_5y_pearson_r").to_csv(OUT / "rolling_correlation_5y.csv")
        print(f"Rolling 60-month correlation: "
              f"min={roll.min():.3f}, mean={roll.mean():.3f}, max={roll.max():.3f}")
    else:
        # for annual data, use a 10-year rolling window
        roll = df["cpi_yoy"].rolling(10).corr(df["ppi_yoy"]).dropna()
        roll.to_frame("rolling_10y_pearson_r").to_csv(OUT / "rolling_correlation_10y.csv")
        print(f"Rolling 10-year correlation: "
              f"min={roll.min():.3f}, mean={roll.mean():.3f}, max={roll.max():.3f}")

    print(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()

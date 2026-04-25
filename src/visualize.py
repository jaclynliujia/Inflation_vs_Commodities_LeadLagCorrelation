"""
visualize.py
------------
Produce the four headline charts referenced in the README:

    outputs/01_timeseries.png         CPI YoY vs PPI YoY through time
    outputs/02_scatter.png            Scatter + OLS fit
    outputs/03_rolling_corr.png       Rolling correlation
    outputs/04_decade_bars.png        Pearson r by decade

Reads from data/merged_yoy.csv (live) or data/annual_snapshot.csv (bundled).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

# Consistent palette
CPI_COLOR = "#2E86AB"
PPI_COLOR = "#E63946"
ACCENT = "#1D3557"
NEUTRAL = "#6C757D"

plt.rcParams.update({
    "figure.figsize": (10, 6),
    "figure.dpi": 110,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
})


def load() -> tuple[pd.DataFrame, str]:
    monthly = DATA / "merged_yoy.csv"
    if monthly.exists():
        df = pd.read_csv(monthly, parse_dates=[0], index_col=0).dropna()
        return df, "monthly"
    snap = pd.read_csv(DATA / "annual_snapshot.csv")
    snap["cpi_yoy"] = (snap["cpi_index"] / snap["cpi_index"].shift(1) - 1) * 100
    snap["ppi_yoy"] = (
        snap["ppi_commodities_index"] / snap["ppi_commodities_index"].shift(1) - 1
    ) * 100
    snap = snap.dropna().set_index("year")[["cpi_yoy", "ppi_yoy"]]
    return snap, "annual"


def chart_timeseries(df: pd.DataFrame, freq: str) -> None:
    fig, ax = plt.subplots()
    ax.plot(df.index, df["cpi_yoy"], color=CPI_COLOR, lw=1.8, label="CPI YoY %")
    ax.plot(df.index, df["ppi_yoy"], color=PPI_COLOR, lw=1.4, alpha=0.85,
            label="PPI: All Commodities YoY %")
    ax.axhline(0, color=NEUTRAL, lw=0.8, ls="--", alpha=0.6)
    ax.set_title(f"US Inflation vs Commodity Prices ({freq.title()} YoY % change, "
                 f"{df.index.min()}–{df.index.max()})")
    ax.set_xlabel("")
    ax.set_ylabel("Year-over-year change (%)")
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "01_timeseries.png")
    plt.close(fig)


def chart_scatter(df: pd.DataFrame) -> None:
    slope, intercept, r, p, _ = stats.linregress(df["ppi_yoy"], df["cpi_yoy"])
    x = df["ppi_yoy"].values
    y = df["cpi_yoy"].values

    fig, ax = plt.subplots()
    ax.scatter(x, y, color=CPI_COLOR, alpha=0.55, s=28, edgecolor="white", linewidth=0.5)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, intercept + slope * xs, color=ACCENT, lw=2,
            label=f"OLS: y = {intercept:.2f} + {slope:.3f}·x   "
                  f"R² = {r ** 2:.3f}   p = {p:.1e}")
    ax.axhline(0, color=NEUTRAL, lw=0.7, ls="--", alpha=0.5)
    ax.axvline(0, color=NEUTRAL, lw=0.7, ls="--", alpha=0.5)
    ax.set_title("CPI YoY vs PPI: All Commodities YoY")
    ax.set_xlabel("PPI: All Commodities YoY %")
    ax.set_ylabel("CPI YoY %")
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "02_scatter.png")
    plt.close(fig)


def chart_rolling(df: pd.DataFrame, freq: str) -> None:
    if freq == "monthly":
        win = 60
        roll = df["cpi_yoy"].rolling(win).corr(df["ppi_yoy"]).dropna()
        title = "60-month rolling Pearson correlation"
    else:
        win = 10
        roll = df["cpi_yoy"].rolling(win).corr(df["ppi_yoy"]).dropna()
        title = "10-year rolling Pearson correlation"

    fig, ax = plt.subplots()
    ax.plot(roll.index, roll.values, color=ACCENT, lw=2)
    ax.fill_between(roll.index, 0, roll.values,
                    where=roll.values >= 0, color=CPI_COLOR, alpha=0.18)
    ax.fill_between(roll.index, 0, roll.values,
                    where=roll.values < 0, color=PPI_COLOR, alpha=0.18)
    ax.axhline(0, color=NEUTRAL, lw=0.8, ls="--")
    ax.axhline(roll.mean(), color=NEUTRAL, lw=0.8, ls=":",
               label=f"Mean r = {roll.mean():.2f}")
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("Pearson r")
    ax.set_ylim(-1.05, 1.05)
    ax.legend(loc="lower left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "03_rolling_corr.png")
    plt.close(fig)


def chart_decades(df: pd.DataFrame, freq: str) -> None:
    s = df.copy()
    s["decade"] = (s.index.year if freq == "monthly" else s.index) // 10 * 10
    rows = []
    for d, g in s.groupby("decade"):
        if len(g) < 5:
            continue
        r, _ = stats.pearsonr(g["cpi_yoy"], g["ppi_yoy"])
        rows.append((f"{int(d)}s", r, len(g)))
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    ns = [r[2] for r in rows]

    colors = [CPI_COLOR if v >= 0 else PPI_COLOR for v in values]
    fig, ax = plt.subplots()
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=1.5)
    ax.axhline(0, color=NEUTRAL, lw=0.8)
    ax.set_ylim(-1.05, 1.05)
    ax.set_title("Pearson correlation by decade (CPI YoY vs PPI: All Commodities YoY)")
    ax.set_ylabel("Pearson r")
    for bar, v, n in zip(bars, values, ns):
        ax.text(bar.get_x() + bar.get_width() / 2,
                v + (0.05 if v >= 0 else -0.09),
                f"r={v:.2f}\nn={n}",
                ha="center", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "04_decade_bars.png")
    plt.close(fig)


def main() -> None:
    df, freq = load()
    chart_timeseries(df, freq)
    chart_scatter(df)
    chart_rolling(df, freq)
    chart_decades(df, freq)
    print(f"Wrote 4 charts to {OUT} (using {freq} data, n={len(df)})")


if __name__ == "__main__":
    main()

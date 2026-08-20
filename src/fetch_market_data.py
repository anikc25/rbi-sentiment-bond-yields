"""
Pull the one market series that's actually available via a free API:
USD/INR daily close, via yfinance.

The 10Y G-Sec yield, CPI surprise, and repo-rate history are NOT fetched
here — see the README for why those are manual downloads / hand-built CSVs,
and save them directly into data/market/ under the filenames paths.py expects:
    data/market/india_10y_gsec_raw.csv
    data/market/cpi_surprise.csv
    data/market/repo_rate_history.csv

Run from anywhere:
    python src/fetch_market_data.py

Output:
    data/market/usdinr_daily.csv   (clean two-column CSV: date, usdinr)
"""
import pandas as pd
import yfinance as yf

try:
    from paths import USDINR_CSV
except ImportError:
    from src.paths import USDINR_CSV

START = "2016-09-01"
END = None  # None = up to today


def main():
    fx = yf.download("INR=X", start=START, end=END, progress=False, auto_adjust=False)
    if fx.empty:
        raise RuntimeError("yfinance returned no data — check your internet connection / ticker.")

    # newer yfinance versions return a MultiIndex column (Price, Ticker) even
    # for a single ticker -- flatten it so the saved CSV has one clean header row
    if isinstance(fx.columns, pd.MultiIndex):
        fx.columns = fx.columns.get_level_values(0)

    fx = fx[["Close"]].rename(columns={"Close": "usdinr"})
    fx.index.name = "date"
    fx.to_csv(USDINR_CSV)
    print(f"Saved {len(fx)} rows -> {USDINR_CSV}")
    print(fx.tail())


if __name__ == "__main__":
    main()

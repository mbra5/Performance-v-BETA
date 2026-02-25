"""
Data fetching and calculation module for the Performance vs. Beta dashboard.

Logic mirrors the Excel model:
  - Stock price history (column E in Excel)
  - Rolling 6-month beta = cov(stock_ret, index_ret) / var(index_ret)  over 126 trading days
  - Beta-implied return = beta * index_return_over_window
  - Perf vs Beta = actual_stock_return - beta_implied_return
  Computed for three windows: 2W (10 days), 4W (20 days), 12W (60 days)
"""

import warnings
import numpy as np
import pandas as pd
import yfinance as yf

# Map index display names to yfinance tickers
INDEX_MAP = {
    "SPX":  "^GSPC",
    "NDX":  "^NDX",
    "RTY":  "^RUT",
    "DJIA": "^DJI",
}

WINDOWS = {
    "2W":  10,   # 2 calendar weeks ~ 10 trading days
    "4W":  20,
    "12W": 60,
}

BETA_WINDOW = 126   # ~6 calendar months of trading days


def get_company_name(ticker: str) -> str:
    """Return the long company name for a ticker, or the ticker itself on failure."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return ticker


def load_data(
    ticker: str,
    index_key: str = "SPX",
    period: str = "3y",
) -> tuple[pd.DataFrame, str]:
    """
    Download price history for ticker and index, then compute all metrics.

    Returns
    -------
    df : pd.DataFrame
        Columns: date, stock_price, index_price, beta,
                 stock_ret_2W/4W/12W, index_ret_2W/4W/12W,
                 beta_implied_2W/4W/12W, perf_vs_beta_2W/4W/12W
    error : str
        Empty string on success, error message on failure.
    """
    index_yfin = INDEX_MAP.get(index_key.upper(), f"^{index_key}")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw_stock = yf.download(ticker, period=period, interval="1d",
                                    auto_adjust=True, progress=False)
            raw_index = yf.download(index_yfin, period=period, interval="1d",
                                    auto_adjust=True, progress=False)
    except Exception as e:
        return pd.DataFrame(), str(e)

    if raw_stock.empty:
        return pd.DataFrame(), f"No data found for ticker '{ticker}'. Check the symbol."
    if raw_index.empty:
        return pd.DataFrame(), f"No data found for index '{index_key}'."

    # Extract closing prices — handle MultiIndex columns from yfinance v0.2+
    def extract_close(raw):
        if isinstance(raw.columns, pd.MultiIndex):
            return raw["Close"].iloc[:, 0]
        return raw["Close"]

    stock_px = extract_close(raw_stock).rename("stock_price")
    index_px = extract_close(raw_index).rename("index_price")

    # Align to common trading days
    df = pd.concat([stock_px, index_px], axis=1).dropna()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # Daily returns
    df["stock_daily"] = df["stock_price"].pct_change()
    df["index_daily"] = df["index_price"].pct_change()

    # Rolling 6M beta (126-day rolling window)
    df["beta"] = _rolling_beta(df["stock_daily"], df["index_daily"], BETA_WINDOW)

    # Per-timeframe metrics
    for label, days in WINDOWS.items():
        s_ret = df["stock_price"].pct_change(days)
        i_ret = df["index_price"].pct_change(days)
        b_imp = df["beta"] * i_ret
        pvb   = s_ret - b_imp

        df[f"stock_ret_{label}"]    = s_ret
        df[f"index_ret_{label}"]    = i_ret
        df[f"beta_implied_{label}"] = b_imp
        df[f"perf_vs_beta_{label}"] = pvb

    df = df.reset_index().rename(columns={"Date": "date", "index": "date"})
    # Ensure the date column is named "date" regardless of yfinance version
    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "date"})

    return df, ""


def _rolling_beta(stock_ret: pd.Series, index_ret: pd.Series, window: int) -> pd.Series:
    """Vectorised rolling beta using pandas rolling covariance / variance."""
    cov = stock_ret.rolling(window).cov(index_ret)
    var = index_ret.rolling(window).var()
    beta = cov / var
    return beta

"""
Data fetching and calculation module for the Performance vs. Beta dashboard.

Logic mirrors the Excel model:
  - Stock price history (column E in Excel)
  - Rolling 6-month beta = cov(stock_ret, index_ret) / var(index_ret)  over 126 trading days
  - Beta-implied return = beta * index_return_over_window
  - Perf vs Beta = actual_stock_return - beta_implied_return
  Computed for three windows: 2W (10 days), 4W (20 days), 12W (60 days)
"""

import re
import warnings
import numpy as np
import pandas as pd
import yfinance as yf

# Map index display names to yfinance tickers
INDEX_MAP = {
    "SPX":   "^GSPC",
    "NDX":   "^NDX",
    "RTY":   "^RUT",
    "DJIA":  "^DJI",
    "TWSE":  "^TWII",    # Taiwan Weighted Index
    "NKY":   "^N225",    # Nikkei 225
    "FTSE":  "^FTSE",    # FTSE 100
    "DAX":   "^GDAXI",   # German DAX
    "CAC":   "^FCHI",    # CAC 40
    "HSI":   "^HSI",     # Hang Seng
    "KOSPI": "^KS11",    # Korea KOSPI
    "ASX200":"^AXJO",    # Australia ASX 200
}

# Bloomberg exchange suffix → (yfinance suffix, home index key)
BLOOMBERG_EXCHANGE_MAP = {
    "TT": (".TW",  "TWSE"),    # Taiwan
    "JT": (".T",   "NKY"),     # Japan (Tokyo)
    "LN": (".L",   "FTSE"),    # UK London
    "FP": (".PA",  "CAC"),     # France Paris
    "GY": (".DE",  "DAX"),     # Germany Xetra
    "IM": (".MI",  "DAX"),     # Italy Milan
    "NA": (".AS",  "DAX"),     # Netherlands Amsterdam
    "SM": (".MC",  "DAX"),     # Spain Madrid
    "HK": (".HK",  "HSI"),     # Hong Kong
    "AU": (".AX",  "ASX200"),  # Australia
    "KS": (".KS",  "KOSPI"),   # Korea KSE
    "KP": (".KQ",  "KOSPI"),   # Korea KOSDAQ
    "SP": (".SI",  "SPX"),     # Singapore
}


def normalize_ticker(raw: str) -> tuple:
    """
    Normalize a Bloomberg-style ticker to yfinance format.

    Handles:
      "2330 TT"  → ("2330.TW", "TWSE", "TT")
      "9984 JT"  → ("9984.T",  "NKY",  "JT")
      "CRH LN"   → ("CRH.L",   "FTSE", "LN")
      "CRH US"   → ("CRH",     "SPX",  "US")
      "AAPL"     → ("AAPL",    None,   None)   ← no change

    Returns (yfinance_ticker, suggested_index_key, detected_exchange_code).
    """
    raw = raw.strip().upper()
    raw = re.sub(r"\s+EQUITY\s*$", "", raw)  # strip trailing " EQUITY"

    parts = raw.split()
    if len(parts) == 2:
        base, exch = parts
        if exch == "US":
            return base, "SPX", "US"
        if exch in BLOOMBERG_EXCHANGE_MAP:
            suffix, idx = BLOOMBERG_EXCHANGE_MAP[exch]
            return base + suffix, idx, exch

    return raw.replace(" ", ""), None, None


# yfinance exchange suffix → home index (for reverse-lookup after symbol selection)
YFINANCE_SUFFIX_INDEX_MAP = {
    "TW": "TWSE", "T":  "NKY",   "L":  "FTSE",
    "PA": "CAC",  "DE": "DAX",   "MI": "DAX",
    "AS": "DAX",  "MC": "DAX",   "HK": "HSI",
    "AX": "ASX200", "KS": "KOSPI", "KQ": "KOSPI",
}


def search_ticker(query: str, max_results: int = 5) -> list:
    """Search Yahoo Finance; returns list of {symbol, name, exchange}."""
    try:
        import requests
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={requests.utils.quote(query)}"
            f"&quotesCount={max_results}&newsCount=0&listsCount=0"
        )
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = resp.json()
        out = []
        for q in data.get("quotes", []):
            if q.get("quoteType") not in ("EQUITY", "ETF"):
                continue
            out.append({
                "symbol": q["symbol"],
                "name": q.get("shortname") or q.get("longname") or q["symbol"],
                "exchange": q.get("exchange", ""),
            })
        return out[:max_results]
    except Exception:
        return []


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
    start_date=None,
    end_date=None,
) -> tuple:
    """
    Download price history for ticker and index, then compute all metrics.

    If start_date and end_date are provided (datetime.date or str), they
    override `period` and disk-cache is bypassed for that request.

    Returns
    -------
    df : pd.DataFrame
        Columns: date, stock_price, index_price, beta,
                 stock_ret_2W/4W/12W, index_ret_2W/4W/12W,
                 beta_implied_2W/4W/12W, perf_vs_beta_2W/4W/12W
    error : str
        Empty string on success, error message on failure.
    """
    index_yfin  = INDEX_MAP.get(index_key.upper(), f"^{index_key}")
    use_custom  = start_date is not None and end_date is not None

    # ── Helper: extract close from a raw yfinance DataFrame ─────────────────
    def extract_close(raw):
        for col_name in ("Close", "Adj Close"):
            if isinstance(raw.columns, pd.MultiIndex):
                if col_name in raw.columns.get_level_values(0):
                    s = raw[col_name]
                    return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
            elif col_name in raw.columns:
                return raw[col_name]
        raise ValueError(f"No close price column found; got: {list(raw.columns)[:5]}")

    # ── Try disk cache (standard periods only) ───────────────────────────────
    stock_px = index_px = None
    if not use_custom:
        try:
            from pre_cache import load_price_series
            s = load_price_series(ticker, period)
            if s is not None:
                stock_px = s.rename("stock_price")
            s = load_price_series(index_yfin, period)
            if s is not None:
                index_px = s.rename("index_price")
        except ImportError:
            pass

    # ── Download whatever is still missing from yfinance ────────────────────
    raw_stock = raw_index = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            kw = dict(interval="1d", auto_adjust=True, progress=False)
            if use_custom:
                import datetime as _dt
                kw["start"] = start_date
                # yfinance end is exclusive; add one day to include end_date
                kw["end"] = (
                    end_date + _dt.timedelta(days=1)
                    if hasattr(end_date, "year") else end_date
                )
            else:
                kw["period"] = period

            if stock_px is None:
                raw_stock = yf.download(ticker, **kw)
            if index_px is None:
                raw_index = yf.download(index_yfin, **kw)
    except Exception as e:
        return pd.DataFrame(), str(e)

    # ── Extract close prices from raw downloads ──────────────────────────────
    if stock_px is None:
        if raw_stock is None or raw_stock.empty:
            return pd.DataFrame(), f"No data found for ticker '{ticker}'. Check the symbol."
        stock_px = extract_close(raw_stock).rename("stock_price")
        # Persist to disk cache for future requests
        if not use_custom:
            try:
                from pre_cache import save_price_series, is_cache_fresh, price_cache_path
                if not is_cache_fresh(price_cache_path(ticker, period)):
                    save_price_series(ticker, stock_px, period)
            except ImportError:
                pass

    if index_px is None:
        if raw_index is None or raw_index.empty:
            return pd.DataFrame(), f"No data found for index '{index_key}'."
        index_px = extract_close(raw_index).rename("index_price")
        if not use_custom:
            try:
                from pre_cache import save_price_series, is_cache_fresh, price_cache_path
                if not is_cache_fresh(price_cache_path(index_yfin, period)):
                    save_price_series(index_yfin, index_px, period)
            except ImportError:
                pass

    # ── Strip timezone so both series share a tz-naive DatetimeIndex ─────────
    if isinstance(stock_px.index, pd.DatetimeIndex) and stock_px.index.tz is not None:
        stock_px.index = stock_px.index.tz_localize(None)
    if isinstance(index_px.index, pd.DatetimeIndex) and index_px.index.tz is not None:
        index_px.index = index_px.index.tz_localize(None)

    # ── Align to common trading days ─────────────────────────────────────────
    df = pd.concat([stock_px, index_px], axis=1).dropna()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # ── Daily returns ────────────────────────────────────────────────────────
    df["stock_daily"] = df["stock_price"].pct_change()
    df["index_daily"] = df["index_price"].pct_change()

    # ── Rolling 6M beta (126-day rolling window) ─────────────────────────────
    df["beta"] = _rolling_beta(df["stock_daily"], df["index_daily"], BETA_WINDOW)

    # ── Per-timeframe metrics ────────────────────────────────────────────────
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

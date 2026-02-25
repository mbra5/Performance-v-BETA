"""
Pre-cache module for Performance vs. Beta dashboard.

Fetches and stores price histories for:
  - S&P 500 (Wikipedia)
  - S&P MidCap 400 + SmallCap 600 = S&P 1000 (Wikipedia)
  - Nasdaq-100 / QQQ (Wikipedia)
  - All dashboard indices (INDEX_MAP)

Runs pre_fetch_all() at startup (skips already-fresh files) and
schedules a daily 4:15 PM refresh via a background daemon thread.
"""

import os
import time
import threading
import datetime
import warnings
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR            = os.path.join(os.path.dirname(__file__), "cache")
CACHE_MAX_AGE_HOURS  = 6.0   # files younger than this are considered fresh
DEFAULT_PERIOD       = "3y"  # price window to pre-fetch


# ── Disk-cache helpers ──────────────────────────────────────────────────────

def price_cache_path(ticker: str, period: str = DEFAULT_PERIOD) -> str:
    """Parquet file path for cached close-price series."""
    safe = (ticker.replace("/", "_").replace(".", "_")
                  .replace("^", "X").replace("-", "_"))
    return os.path.join(CACHE_DIR, f"{safe}__{period}.parquet")


def is_cache_fresh(path: str, max_age_hours: float = CACHE_MAX_AGE_HOURS) -> bool:
    if not os.path.exists(path):
        return False
    return (time.time() - os.path.getmtime(path)) / 3600 < max_age_hours


def save_price_series(ticker: str, series: pd.Series,
                      period: str = DEFAULT_PERIOD) -> None:
    """Save a close-price Series to disk (tz-stripped, parquet)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    s = series.copy()
    if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    s.to_frame("close").to_parquet(price_cache_path(ticker, period))


def load_price_series(ticker: str,
                      period: str = DEFAULT_PERIOD) -> "pd.Series | None":
    """Return cached close-price Series, or None if stale / missing."""
    path = price_cache_path(ticker, period)
    if not is_cache_fresh(path):
        return None
    try:
        return pd.read_parquet(path)["close"]
    except Exception:
        return None


# ── Universe list fetchers ──────────────────────────────────────────────────

def get_sp500_tickers() -> list:
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            attrs={"id": "constituents"},
        )
        return [str(t).replace(".", "-") for t in tables[0]["Symbol"].tolist()]
    except Exception as e:
        logger.warning(f"S&P 500 list fetch failed: {e}")
        return []


def get_sp400_tickers() -> list:
    """S&P MidCap 400 from Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_Mid-Cap_400_companies"
        )
        for t in tables:
            for col in ("Symbol", "Ticker"):
                if col in t.columns and len(t) > 50:
                    return [str(s).replace(".", "-")
                            for s in t[col].dropna().tolist()]
    except Exception as e:
        logger.warning(f"S&P 400 list fetch failed: {e}")
    return []


def get_sp600_tickers() -> list:
    """S&P SmallCap 600 from Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
        )
        for t in tables:
            for col in ("Symbol", "Ticker"):
                if col in t.columns and len(t) > 50:
                    return [str(s).replace(".", "-")
                            for s in t[col].dropna().tolist()]
    except Exception as e:
        logger.warning(f"S&P 600 list fetch failed: {e}")
    return []


def get_qqq_tickers() -> list:
    """Nasdaq-100 (QQQ) from Wikipedia."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        for t in tables:
            for col in ("Ticker", "Symbol"):
                if col in t.columns and len(t) > 80:
                    return [str(s) for s in t[col].dropna().tolist()
                            if isinstance(s, str) and 1 < len(s) <= 8]
    except Exception as e:
        logger.warning(f"QQQ list fetch failed: {e}")
    return []


def get_universe_tickers() -> list:
    """Union of S&P 500, S&P 1000 (400+600), and QQQ — deduped, sorted."""
    all_tickers = set(
        get_sp500_tickers()
        + get_sp400_tickers()
        + get_sp600_tickers()
        + get_qqq_tickers()
    )
    return sorted([t for t in all_tickers if t and 1 <= len(t) <= 8])


# ── Batch pre-fetch ─────────────────────────────────────────────────────────

def _extract_close_multi(raw: pd.DataFrame, ticker: str) -> "pd.Series | None":
    """Pull the Close series for one ticker from a multi-ticker download."""
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            lvl0 = raw.columns.get_level_values(0).unique().tolist()
            if ticker in lvl0:
                sub = raw[ticker]
                for col in ("Close", "Adj Close"):
                    if col in sub.columns:
                        s = sub[col]
                        return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
        else:
            for col in ("Close", "Adj Close"):
                if col in raw.columns:
                    return raw[col]
    except Exception:
        pass
    return None


def pre_fetch_batch(tickers: list, period: str = DEFAULT_PERIOD,
                    chunk_size: int = 100) -> None:
    """Download and cache close prices for tickers; skips fresh files."""
    stale = [t for t in tickers
             if not is_cache_fresh(price_cache_path(t, period))]
    if not stale:
        return

    logger.info(f"Pre-fetching {len(stale)} tickers (period={period})")

    for i in range(0, len(stale), chunk_size):
        chunk = stale[i: i + chunk_size]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if len(chunk) == 1:
                    raw = yf.download(
                        chunk[0], period=period, interval="1d",
                        auto_adjust=True, progress=False,
                    )
                    s = _extract_close_multi(raw, chunk[0])
                    if s is None:
                        for col in ("Close", "Adj Close"):
                            if col in raw.columns:
                                s = raw[col]
                                break
                    if s is not None and not s.empty:
                        save_price_series(chunk[0], s, period)
                else:
                    raw = yf.download(
                        chunk, period=period, interval="1d",
                        auto_adjust=True, progress=False,
                        group_by="ticker",
                    )
                    for t in chunk:
                        s = _extract_close_multi(raw, t)
                        if s is not None and not s.empty:
                            save_price_series(t, s, period)
        except Exception as e:
            logger.warning(f"Chunk {i // chunk_size} pre-fetch failed: {e}")
        time.sleep(0.3)   # brief pause to avoid rate-limits


def pre_fetch_all(period: str = DEFAULT_PERIOD) -> None:
    """Pre-fetch all dashboard indices + equity universe."""
    try:
        from data import INDEX_MAP
        idx_tickers = list(INDEX_MAP.values())   # "^GSPC", "^NDX", etc.
        logger.info("Pre-fetching indices…")
        pre_fetch_batch(idx_tickers, period=period,
                        chunk_size=len(idx_tickers))
    except Exception as e:
        logger.warning(f"Index pre-fetch failed: {e}")

    try:
        tickers = get_universe_tickers()
        logger.info(f"Pre-fetching equity universe ({len(tickers)} tickers)…")
        pre_fetch_batch(tickers, period=period)
    except Exception as e:
        logger.warning(f"Equity universe pre-fetch failed: {e}")


# ── Scheduler ───────────────────────────────────────────────────────────────

_started = False
_lock    = threading.Lock()


def start_scheduler() -> None:
    """
    Start a background daemon thread that:
      1. Runs pre_fetch_all() on startup (skipping already-fresh files).
      2. Waits until the next 4:15 PM, then repeats daily.

    Thread-safe — subsequent calls are no-ops.
    """
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def _loop() -> None:
        try:
            pre_fetch_all()
        except Exception as e:
            logger.error(f"Startup pre-fetch error: {e}")

        while True:
            now    = datetime.datetime.now()
            target = now.replace(hour=16, minute=15, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            wait_s = (target - now).total_seconds()
            logger.info(
                f"Cache scheduler: next refresh at "
                f"{target.strftime('%Y-%m-%d %H:%M')} "
                f"(in {wait_s / 3600:.1f} h)"
            )
            time.sleep(wait_s)
            try:
                pre_fetch_all()
            except Exception as e:
                logger.error(f"Scheduled pre-fetch error: {e}")

    t = threading.Thread(target=_loop, daemon=True, name="CacheScheduler")
    t.start()

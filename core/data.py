# -*- coding: utf-8 -*-
"""
MARKET_ISOLATION_LAYER - 数据获取层 (架构模块2)
================================================
- US_EQUITY_PROFILE: yfinance 日线 (RTH, split+dividend adjusted)
- CRYPTO_PROFILE: ccxt 小时线 (7x24, 聚合OHLCV)
缓存到 data/ 目录 (parquet), 幂等。
用法:
  python scripts/fetch_data.py --symbol BTC/USDT --profile crypto --tf 1h
  python scripts/fetch_data.py --symbol SPY AAPL --profile equity
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _cache_path(symbol: str, profile: str, tf: str) -> Path:
    safe = symbol.replace("/", "_").replace(":", "")
    return DATA_DIR / f"{profile}_{safe}_{tf}.parquet"


def fetch_equity(symbol: str, years: int = 6) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(symbol, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index).tz_localize("America/New_York") \
        if df.index.tz is None else df.index.tz_convert("America/New_York")
    # RTH 过滤: 仅常规交易时段 (yfinance日线本身即RTH)
    return df.sort_index()


def fetch_crypto(symbol: str, tf: str = "1h", days: int = 730) -> pd.DataFrame:
    import ccxt

    ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    since = ex.milliseconds() - days * 86400 * 1000
    all_ohlcv: list = []
    while since < ex.milliseconds():
        batch = ex.fetch_ohlcv(symbol, timeframe=tf, since=since, limit=1000)
        if not batch:
            break
        all_ohlcv.extend(batch)
        since = batch[-1][0] + 1
    df = pd.DataFrame(all_ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop_duplicates("ts").set_index("ts").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def load_data(symbol: str, profile: str, tf: str = "1d",
              force_refresh: bool = False) -> pd.DataFrame:
    """带缓存的加载入口。profile: 'equity' | 'crypto'。"""
    DATA_DIR.mkdir(exist_ok=True)
    path = _cache_path(symbol, profile, tf)
    if path.exists() and not force_refresh:
        return pd.read_parquet(path)
    df = fetch_equity(symbol) if profile == "equity" else fetch_crypto(symbol, tf)
    df.to_parquet(path)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", nargs="+", required=True)
    ap.add_argument("--profile", choices=["equity", "crypto"], default="equity")
    ap.add_argument("--tf", default="1d")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    for s in args.symbol:
        df = load_data(s, args.profile, args.tf, force_refresh=args.force)
        print(f"[data] {s} ({args.profile} {args.tf}): {len(df)} bars, "
              f"{df.index[0]} -> {df.index[-1]}")


if __name__ == "__main__":
    sys.exit(main())

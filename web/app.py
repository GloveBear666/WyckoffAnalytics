# -*- coding: utf-8 -*-
"""
WYCKOFFANALYTICS WEB 可视终端 - 后端 (Flask)
=============================================
功能:
  - GET  /api/status        数据/配置/温度参数
  - POST /api/backtest      一键回测 (温度T/窗口/冷却/HTF可调)
  - POST /api/grid          温度扫描 T∈[0.1,1.0]
  - GET  /                  前端页面 (web/static/index.html)

启动: python web/app.py  (默认 http://127.0.0.1:8088)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, request, send_from_directory

from core.backtest import run_backtest
from core.data import load_data
from core.signals import generate_signals, summarize_signals, temperature_params
from core.training import train_round, training_history

app = Flask(__name__, static_folder=str(ROOT / "web" / "static"), static_url_path="/static")

PROFILE_MAP = {"crypto": "CRYPTO_PROFILE", "equity": "US_EQUITY_PROFILE"}
DATA_DIR = ROOT / "data"

# 数据缓存: (profile, symbol, tf) -> DataFrame
_DATA_CACHE: dict = {}
_MAX_CHART_POINTS = 2000
_MAX_TRADES = 1000


class ApiError(Exception):
    """业务错误 -> HTTP 400 JSON。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@app.errorhandler(ApiError)
def handle_api_error(e: ApiError):
    return jsonify({"error": e.message}), 400


@app.errorhandler(Exception)
def handle_unexpected(e: Exception):
    import traceback
    traceback.print_exc()
    return jsonify({"error": f"服务器内部错误: {e}"}), 500


def _list_datasets() -> list[dict]:
    out = []
    for p in sorted(DATA_DIR.glob("*.parquet")):
        parts = p.stem.split("_")
        if len(parts) >= 3:
            profile, tf = parts[0], parts[-1]
            symbol = "_".join(parts[1:-1])  # 符号可含下划线 (如 BTC_USDT)
            out.append({"profile": profile, "symbol": symbol, "tf": tf, "file": p.name})
    return out


def _get_data(profile: str, symbol: str, tf: str):
    key = (profile, symbol, tf)
    if key not in _DATA_CACHE:
        try:
            _DATA_CACHE[key] = load_data(symbol, profile, tf)
        except Exception as e:  # noqa: BLE001
            raise ApiError(
                f"无法获取 {symbol} ({profile}/{tf}): {e}. "
                f"提示: {symbol} 必须与市场配置匹配 (crypto 用加密货币代码如 BTC/USDT, equity 用美股代码如 AAPL). "
                f"也可先用 CLI 抓取: python core/data.py --profile {profile} --symbol {symbol} --tf {tf}") from e
    return _DATA_CACHE[key]


def _metric_payload(metrics: dict) -> dict:
    return {k: float(v) for k, v in metrics.items()}


def _chart_series(equity) -> tuple[list, list]:
    """下采样净值与回撤序列供前端绘图。"""
    n = len(equity)
    step = max(1, n // _MAX_CHART_POINTS)
    eq = equity.iloc[::step]
    dd = (eq / eq.cummax() - 1)
    dates = [t.isoformat() for t in eq.index]
    return dates, [round(float(v), 6) for v in eq.values], [round(float(v), 6) for v in dd.values]


@app.get("/")
def index():
    return send_from_directory(str(ROOT / "web" / "static"), "index.html")


@app.get("/api/status")
def status():
    t = temperature_params(0.5)
    return jsonify({
        "datasets": _list_datasets(),
        "profiles": {k: v["description"] for k, v in
                     json.loads((ROOT / "config" / "market_profiles.json").read_text(encoding="utf-8"))["profiles"].items()},
        "temperature_params_05": {k: v for k, v in t.items() if k != "T"},
    })


@app.get("/api/temperature")
def temperature():
    T = float(request.args.get("T", 0.5))
    return jsonify(temperature_params(T))


@app.post("/api/backtest")
def backtest():
    body = request.get_json(force=True)
    prof = PROFILE_MAP[body.get("profile", "crypto")]   # 回测配置
    dprof = body.get("profile", "crypto")               # 数据层 profile
    symbol = body.get("symbol", "BTC/USDT")
    tf = body.get("tf", "1h")
    T = float(body.get("T", 0.5))
    fw = int(body.get("feature_window", 60))
    mh = int(body.get("max_bars_hold", 60))
    cd = int(body.get("entry_cooldown", 5))
    htf_tf = body.get("htf_tf")

    if not symbol or not tf:
        raise ApiError("缺少 symbol/tf 参数")
    df = _get_data(dprof, symbol, tf)
    htf = _get_data(dprof, symbol, htf_tf) if htf_tf else None
    sig = generate_signals(df, T=T, feature_window=fw, entry_cooldown=cd, htf=htf)
    res = run_backtest(df, sig, T=T, profile=prof, max_bars_hold=mh, entry_cooldown=cd)

    dates, eq, dd = _chart_series(res.equity)
    trades = [{
        "entry_dt": t.entry_dt.isoformat(), "exit_dt": t.exit_dt.isoformat(),
        "dir": t.direction, "setup": t.setup, "entry": round(t.entry, 4),
        "exit": round(t.exit, 4), "pnl_pct": round(t.pnl_pct * 100, 2),
        "exit_reason": t.exit_reason, "bars_held": t.bars_held,
    } for t in res.trades[:_MAX_TRADES]]

    return jsonify({
        "symbol": symbol, "tf": tf, "htf_tf": htf_tf, "profile": prof,
        "params": {"T": T, "feature_window": fw, "max_bars_hold": mh, "entry_cooldown": cd},
        "metrics": _metric_payload(res.metrics),
        "signals_summary": summarize_signals(sig),
        "equity": eq, "drawdown": dd, "dates": dates,
        "trades": trades, "n_trades_total": len(res.trades),
    })


@app.post("/api/grid")
def grid():
    body = request.get_json(force=True)
    prof = PROFILE_MAP[body.get("profile", "crypto")]
    dprof = body.get("profile", "crypto")
    symbol = body.get("symbol", "BTC/USDT")
    tf = body.get("tf", "1h")
    fw = int(body.get("feature_window", 60))
    mh = int(body.get("max_bars_hold", 60))
    cd = int(body.get("entry_cooldown", 5))
    htf_tf = body.get("htf_tf")

    df = _get_data(dprof, symbol, tf)
    htf = _get_data(dprof, symbol, htf_tf) if htf_tf else None
    rows = []
    for T in (0.1, 0.3, 0.5, 0.7, 1.0):
        sig = generate_signals(df, T=T, feature_window=fw, entry_cooldown=cd, htf=htf)
        res = run_backtest(df, sig, T=T, profile=prof, max_bars_hold=mh, entry_cooldown=cd)
        rows.append({"T": T, "metrics": _metric_payload(res.metrics)})
    return jsonify({"rows": rows})


@app.post("/api/train")
def train():
    """本地 AI 训练: 贝叶斯优化 + Walk-Forward 准确率验证 + 历史记录。
    参数: symbol/profile/tf/htf_tf/trials/min_trades/folds。耗时约1-5分钟。"""
    body = request.get_json(force=True)
    symbol = body.get("symbol", "BTC/USDT")
    profile = body.get("profile", "crypto")
    tf = body.get("tf", "4h")
    htf_tf = body.get("htf_tf")
    trials = int(body.get("trials", 30))
    min_trades = int(body.get("min_trades", 30))
    folds = int(body.get("folds", 4))
    r = train_round(symbol, profile, tf, htf_tf, trials=trials,
                    min_trades=min_trades, folds=folds)
    # JSON 序列化清洗
    r["best_params"] = {k: float(v) for k, v in r["best_params"].items()}
    r["is_metrics"] = {k: float(v) for k, v in r["is_metrics"].items()}
    return jsonify(r)


@app.get("/api/train/history")
def train_history():
    """训练历史 + 当前最优轮次。"""
    return jsonify(training_history())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    print(f"[web] WyckoffAnalytics terminal -> http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, threaded=True)

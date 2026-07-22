import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

try:
    import akshare as ak
except Exception as e:
    ak = None

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)
PORTFOLIO_FILE = BASE / "portfolio.json"
LATEST_FILE = DATA_DIR / "latest.json"
REPORT_FILE = DATA_DIR / "report.txt"
CN_TZ = timezone(timedelta(hours=8))


def now_cn():
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def to_float(x):
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def get_hist(code: str, days: int = 180) -> pd.DataFrame:
    if ak is None:
        raise RuntimeError("akshare not installed")
    start_date = (datetime.now(CN_TZ) - timedelta(days=days * 2)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, adjust="qfq")
    if df is None or df.empty:
        raise RuntimeError("empty market data")
    df = df.rename(columns={
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg"
    })
    for c in ["open", "close", "high", "low", "volume", "amount", "pct_chg"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["close"]).sort_values("date").tail(days).copy()
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    df["rsi14"] = 100 - 100 / (1 + rs)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]
    return df


def assess(stock, hist):
    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else last
    close = float(last["close"])
    prev_close = float(prev["close"])
    day_chg = (close / prev_close - 1) * 100 if prev_close else to_float(last.get("pct_chg"))
    ma20 = to_float(last.get("ma20"))
    ma60 = to_float(last.get("ma60"))
    rsi14 = to_float(last.get("rsi14"))
    vol_ratio = to_float(last.get("vol_ratio"))
    score = 0
    messages = []
    cost = stock.get("cost")
    qty = stock.get("quantity")
    pnl = None
    pnl_pct = None
    market_value = None

    if stock.get("type") == "持仓" and cost:
        pnl_pct = (close / float(cost) - 1) * 100
        if qty:
            pnl = (close - float(cost)) * float(qty)
            market_value = close * float(qty)
        if pnl_pct <= -12:
            score += 4; messages.append("浮亏超过12%，高风险")
        elif pnl_pct <= -8:
            score += 3; messages.append("浮亏超过8%，重点关注")
        elif pnl_pct <= -5:
            score += 2; messages.append("浮亏超过5%，轻度风险")
        elif pnl_pct >= 20:
            messages.append("浮盈超过20%，可考虑提高保护线")

    if ma20 is not None and close < ma20:
        score += 1; messages.append("收盘价低于MA20")
    if ma60 is not None and close < ma60:
        score += 2; messages.append("收盘价低于MA60")
    if day_chg is not None and day_chg <= -4:
        score += 2; messages.append("单日跌幅超过4%")
    if vol_ratio is not None and vol_ratio >= 2 and day_chg is not None and day_chg < 0:
        score += 2; messages.append("放量下跌")
    if rsi14 is not None and rsi14 < 30:
        messages.append("RSI低于30，短线超跌")
    if not messages:
        messages.append("暂无明显风险信号")

    level = "高风险" if score >= 5 else "中风险" if score >= 3 else "低风险" if score >= 1 else "正常"
    return {
        "code": stock["code"], "name": stock["name"], "type": stock["type"],
        "date": str(last["date"].date()), "close": round(close, 3),
        "day_chg_pct": round(day_chg, 2) if day_chg is not None else None,
        "cost": cost, "quantity": qty,
        "market_value": round(market_value, 2) if market_value is not None else None,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "ma5": round(to_float(last.get("ma5")), 3) if to_float(last.get("ma5")) is not None else None,
        "ma20": round(ma20, 3) if ma20 is not None else None,
        "ma60": round(ma60, 3) if ma60 is not None else None,
        "rsi14": round(rsi14, 2) if rsi14 is not None else None,
        "vol_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "risk_level": level, "risk_score": score, "message": "；".join(messages)
    }


def build_report(payload):
    rows = payload["stocks"]
    high = [r for r in rows if r["risk_level"] == "高风险"]
    mid = [r for r in rows if r["risk_level"] == "中风险"]
    total_mv = sum(r.get("market_value") or 0 for r in rows if r["type"] == "持仓")
    total_pnl = sum(r.get("pnl") or 0 for r in rows if r["type"] == "持仓")
    lines = [
        "【A股持仓风险日报】",
        f"更新时间：{payload['updated_at']}",
        f"持仓市值：{total_mv:,.2f}，浮盈亏：{total_pnl:,.2f}",
        f"高风险：{len(high)} 只，中风险：{len(mid)} 只",
        ""
    ]
    for title, arr in [("高风险", high), ("中风险", mid)]:
        if arr:
            lines.append(title + ":")
            for r in arr:
                extra = f"，盈亏 {r['pnl_pct']}%" if r.get("pnl_pct") is not None else ""
                lines.append(f"- {r['code']} {r['name']}：{r['risk_level']}{extra}，{r['message']}")
            lines.append("")
    lines.append("全部股票：")
    for r in rows:
        extra = f"，盈亏 {r['pnl_pct']}%" if r.get("pnl_pct") is not None else ""
        lines.append(f"- {r['code']} {r['name']}｜{r['risk_level']}｜收盘 {r['close']}{extra}｜{r['message']}")
    return "\n".join(lines)


def pushplus(title, content):
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    if not token:
        print("PUSHPLUS_TOKEN not set, skip push.")
        return
    resp = requests.post("https://www.pushplus.plus/send", json={
        "token": token,
        "title": title,
        "content": content,
        "template": "txt"
    }, timeout=20)
    print(resp.text)


def main():
    portfolio = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
    stocks = []
    errors = []
    for s in portfolio:
        try:
            hist = get_hist(s["code"])
            stocks.append(assess(s, hist))
        except Exception as e:
            errors.append({"code": s["code"], "name": s["name"], "error": str(e)})
    payload = {"updated_at": now_cn(), "stocks": stocks, "errors": errors}
    LATEST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report(payload)
    if errors:
        report += "\n\n行情失败：\n" + "\n".join([f"- {e['code']} {e['name']}: {e['error']}" for e in errors])
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report)
    if stocks:
        pushplus("A股持仓风险日报", report)


if __name__ == "__main__":
    main()

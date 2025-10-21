
import csv
import os
import sys
import io
import json
from datetime import datetime, timezone
from urllib.request import urlopen, Request

CSV_URL = os.environ.get("CSV_URL", "https://docs.google.com/spreadsheets/d/e/2PACX-1vRT72XsOKNZj_RRIhkJ-sNs_aWkfhAMMYd9sv6dAL7Cdu8wGI704fw9aFtRlQtKow/pub?output=csv")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
RUN_MODE = os.environ.get("RUN_MODE", "summary")  # "summary" or "alerts"
ALERT_UP_THRESHOLD = float(os.environ.get("ALERT_UP_THRESHOLD", "0.10"))
ALERT_DOWN_THRESHOLD = float(os.environ.get("ALERT_DOWN_THRESHOLD", "-0.10"))
STATE_FILE = os.environ.get("STATE_FILE", "last_prices.json")

REQUIRED_HEADERS = [
    "Item Name","Condition","Quantity","Buy Price (USD)","Buy Date",
    "Current Price (USD)","Current Value (USD)","Unrealized Profit (USD)","ROI (%)"
]

def fetch_csv(url: str):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        data = r.read()
    return data.decode("utf-8")

def parse_csv(text: str):
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in reader.fieldnames or []]
    for req in REQUIRED_HEADERS:
        if req not in headers:
            raise ValueError(f"Missing required header: {req}")
    rows = []
    for row in reader:
        norm = {k.strip(): v for k, v in row.items()}
        rows.append(norm)
    return rows

def to_float(x, default=0.0):
    try:
        if isinstance(x, str):
            x = x.strip().replace(",","")
        return float(x)
    except Exception:
        return default

def summarise(rows):
    total_current_value = 0.0
    total_cost_basis = 0.0

    roi_list = []

    for r in rows:
        qty = to_float(r.get("Quantity", 0), 0.0)
        buy_price = to_float(r.get("Buy Price (USD)", 0), 0.0)
        current_price = to_float(r.get("Current Price (USD)", 0), 0.0)

        current_value = qty * current_price
        total_current_value += current_value
        total_cost_basis += qty * buy_price

        # Prefer explicit ROI column; if missing/blank, compute from buy/current
        roi_cell = str(r.get("ROI (%)","")).replace("%","").strip()
        roi_percent = None
        if roi_cell:
            try:
                roi_percent = float(roi_cell)
            except Exception:
                roi_percent = None
        if roi_percent is None and buy_price > 0:
            roi_percent = (current_price - buy_price) / buy_price * 100

        roi_list.append({
            "item": r.get("Item Name",""),
            "condition": r.get("Condition",""),
            "roi": roi_percent if roi_percent is not None else 0.0,
            "current_price": current_price
        })

    unrealized = total_current_value - total_cost_basis
    roi_pct = (unrealized/total_cost_basis*100) if total_cost_basis>0 else 0.0

    roi_list_clean = [x for x in roi_list if x["roi"] is not None]
    gainers = sorted(roi_list_clean, key=lambda x: x["roi"], reverse=True)[:5]
    losers = sorted(roi_list_clean, key=lambda x: x["roi"])[:5]

    return {
        "total_current_value": total_current_value,
        "total_cost_basis": total_cost_basis,
        "unrealized": unrealized,
        "roi_pct": roi_pct,
        "gainers": gainers,
        "losers": losers,
    }

def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def compute_alerts(rows, last_state):
    alerts = []
    new_state = {}

    def key_for(r):
        return f"{r.get('Item Name','')} | {r.get('Condition','')}"

    for r in rows:
        key = key_for(r)
        current_price = to_float(r.get("Current Price (USD)",0),0.0)
        new_state[key] = current_price

        prev_price = last_state.get(key)
        if prev_price and prev_price > 0:
            pct_change = (current_price - prev_price)/prev_price
            if pct_change >= ALERT_UP_THRESHOLD or pct_change <= ALERT_DOWN_THRESHOLD:
                alerts.append({
                    "key": key,
                    "prev": prev_price,
                    "curr": current_price,
                    "pct": pct_change*100
                })

    return alerts, new_state

def post_to_discord(webhook_url, content=None, embed=None):
    import json, urllib.request
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()

def fmt_money(x):
    return f"${x:,.2f}"

def main():
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set", file=sys.stderr)
        sys.exit(2)

    # Fetch & parse
    try:
        csv_text = fetch_csv(CSV_URL)
        rows = parse_csv(csv_text)
    except Exception as e:
        post_to_discord(DISCORD_WEBHOOK_URL, content=f"⚠️ Portfolio fetch error: {e}")
        sys.exit(1)

    now = datetime.now(timezone.utc).astimezone().strftime("%b %d, %Y %I:%M %p %Z")

    if RUN_MODE.lower() == "summary":
        summary = summarise(rows)

        def list_block(items):
            if not items:
                return "_None_"
            lines = []
            for x in items:
                lines.append(f"- **{x['item']}** ({x['condition']}): {x['roi']:.2f}%")
            return "\n".join(lines)

        embed = {
            "title": f"💼 CS2 Portfolio Summary — {now}",
            "description": "Daily summary from your Google Sheet",
            "fields": [
                {"name":"Total Current Value","value": fmt_money(summary["total_current_value"]), "inline": True},
                {"name":"Total Cost Basis","value": fmt_money(summary["total_cost_basis"]), "inline": True},
                {"name":"Unrealized P&L","value": fmt_money(summary["unrealized"]), "inline": True},
                {"name":"ROI %","value": f"{summary['roi_pct']:.2f}%", "inline": True},
                {"name":"Top 5 Gainers (ROI %)","value": list_block(summary["gainers"]), "inline": False},
                {"name":"Top 5 Losers (ROI %)","value": list_block(summary["losers"]), "inline": False},
            ],
            "footer": {"text":"Source: Published CSV portfolio"},
        }
        post_to_discord(DISCORD_WEBHOOK_URL, embed=embed)
        return

    # Alerts
    last = load_state(STATE_FILE)
    alerts, new_state = compute_alerts(rows, last)
    save_state(STATE_FILE, new_state)

    if alerts:
        lines = []
        for a in alerts:
            arrow = "▲" if a["pct"]>0 else "▼"
            lines.append(f"{arrow} **{a['key']}** {a['pct']:.1f}%  ({fmt_money(a['prev'])} → {fmt_money(a['curr'])})")
        content = "🚨 **Intraday Price Alerts** (since last run)\n" + "\n".join(lines)
        post_to_discord(DISCORD_WEBHOOK_URL, content=content)
    else:
        post_to_discord(DISCORD_WEBHOOK_URL, content="✅ No intraday price alerts this run.")

if __name__ == "__main__":
    main()

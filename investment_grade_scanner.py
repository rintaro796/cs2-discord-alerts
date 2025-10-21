
import os, json, sys, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import urllib.error

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TITLE_PREFIX = os.environ.get("TITLE_PREFIX", "CS2 Alert")
TZ_NAME = time.tzname[0] if time.tzname else "Local"

def post_discord(embed=None, content=None):
    import urllib.request
    payload = {}
    if content: payload["content"] = content
    if embed: payload["embeds"] = [embed]
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r: r.read()

def fetch_json(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# Expected ENV:
# INVEST_FEED_URL: JSON array of objects with {item, reason, trend7, trend30, listings_change, supply_note, links:[...]}.

INVEST_FEED_URL = os.environ.get("INVEST_FEED_URL")

def main():
    if not DISCORD_WEBHOOK_URL:
        print("Missing DISCORD_WEBHOOK_URL", file=sys.stderr); sys.exit(2)
    now = datetime.now(timezone.utc).astimezone().strftime("%b %d, %Y %I:%M %p %Z")
    if not INVEST_FEED_URL:
        post_discord(content="⚠️ Investment-grade scanner: No INVEST_FEED_URL configured.")
        return
    try:
        items = fetch_json(INVEST_FEED_URL)
    except Exception as ex:
        post_discord(content=f"⚠️ Investment-grade fetch error: {ex}")
        return
    lines = []
    for x in items[:10]:
        name = x.get("item","?")
        r = x.get("reason","signal")
        t7 = x.get("trend7","?")
        t30 = x.get("trend30","?")
        lst = x.get("listings_change","")
        sup = x.get("supply_note","")
        link = (x.get("links") or [""])[0]
        lines.append(f"• **{name}** — 7d: {t7}, 30d: {t30}  · {lst}  · {sup}  {link}")
    embed = {
        "title": f"🔎 Early Investment-Grade Candidates — {now}",
        "description": "\n".join(lines) or "_No candidates_",
        "footer": { "text": "Signals: Trend + Volume + Listings + Supply + Buzz" }
    }
    post_discord(embed=embed)

if __name__ == "__main__":
    main()

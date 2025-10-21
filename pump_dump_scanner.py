
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
# PUMP_FEED_URL: JSON endpoint returning an array of {item, wear, stattrak, pct24, pct72, volume_note, links:[...]}.
# If you don't have a feed yet, set PUMP_FEED_URL to a temporary JSON (e.g., a GitHub raw gist) that you update.

PUMP_FEED_URL = os.environ.get("PUMP_FEED_URL")  # e.g., your own feed or aggregator
THRESH24 = float(os.environ.get("PUMP_THRESH24", "25"))   # %
THRESH72 = float(os.environ.get("PUMP_THRESH72", "40"))   # %

def main():
    if not DISCORD_WEBHOOK_URL:
        print("Missing DISCORD_WEBHOOK_URL", file=sys.stderr); sys.exit(2)
    now = datetime.now(timezone.utc).astimezone().strftime("%b %d, %Y %I:%M %p %Z")
    if not PUMP_FEED_URL:
        post_discord(content="⚠️ Pump scanner: No PUMP_FEED_URL configured.")
        return
    try:
        items = fetch_json(PUMP_FEED_URL)
    except Exception as ex:
        post_discord(content=f"⚠️ Pump scanner fetch error: {ex}")
        return
    flagged = []
    for x in items:
        p24 = float(x.get("pct24", 0))
        p72 = float(x.get("pct72", 0))
        if p24 >= THRESH24 or p72 >= THRESH72:
            flagged.append(x)
    if not flagged:
        post_discord(content=f"✅ No pump-like moves this run ({now}).")
        return
    lines = []
    for x in flagged[:12]:
        name = x.get("item","?")
        wear = x.get("wear","")
        st = " ST" if x.get("stattrak") else ""
        p24 = x.get("pct24","?")
        p72 = x.get("pct72","?")
        vol = x.get("volume_note","")
        link = (x.get("links") or [""])[0]
        lines.append(f"• **{name}** ({wear}{st}) — 24h: +{p24}%, 72h: +{p72}% {('· '+vol) if vol else ''} {link}")
    embed = {
        "title": f"🚨 Pump-like Moves — {now}",
        "description": "\n".join(lines) or "_None_",
        "footer": { "text": "Sources: Steam · CSFloat · BUFF163 (+ CN buzz if available)" }
    }
    post_discord(embed=embed)

if __name__ == "__main__":
    main()

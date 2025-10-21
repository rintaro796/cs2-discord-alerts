
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
# STICKERS_FEED_URL: JSON array of {name, chg24, chg72, chg7d, direction24, direction72, direction7d, notes, links:[...]}.

STICKERS_FEED_URL = os.environ.get("STICKERS_FEED_URL")

def main():
    if not DISCORD_WEBHOOK_URL:
        print("Missing DISCORD_WEBHOOK_URL", file=sys.stderr); sys.exit(2)
    now = datetime.now(timezone.utc).astimezone().strftime("%b %d, %Y %I:%M %p %Z")
    if not STICKERS_FEED_URL:
        post_discord(content="⚠️ Stickers/Patches: No STICKERS_FEED_URL configured.")
        return
    try:
        items = fetch_json(STICKERS_FEED_URL)
    except Exception as ex:
        post_discord(content=f"⚠️ Stickers/Patches fetch error: {ex}")
        return

    up = []; down = []
    for x in items:
        row = f"• **{x.get('name','?')}** — 24h: {x.get('chg24','?')} / 72h: {x.get('chg72','?')} / 7d: {x.get('chg7d','?')}  {x.get('notes','')} {(x.get('links') or [''])[0]}"
        if x.get("direction24") == "UP" or x.get("direction72") == "UP" or x.get("direction7d") == "UP":
            up.append(row)
        if x.get("direction24") == "DOWN" or x.get("direction72") == "DOWN" or x.get("direction7d") == "DOWN":
            down.append(row)

    embed = {
        "title": f"🎟️ Stickers & Patches — {now}",
        "fields": [
            {"name":"UPWARD Movers (24h/72h/7d)","value": "\n".join(up) or "_None_", "inline": False},
            {"name":"DOWNWARD Movers (24h/72h/7d)","value": "\n".join(down) or "_None_", "inline": False},
        ],
        "footer": { "text": "Cross-ref cases/souvenirs when applicable" }
    }
    post_discord(embed=embed)

if __name__ == "__main__":
    main()

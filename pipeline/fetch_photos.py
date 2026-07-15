"""One-time headshot fetcher.

Downloads player photos hosted by the Scorebook platform into
site/public/headshots/{slug}.jpg and prints the players.yaml lines to add.
Players on other platforms keep the initials placeholder until sourced
(GT athletics / previous-school photos are a manual research task).

Usage: .venv/bin/python -m pipeline.fetch_photos
"""
import sys
import time
from pathlib import Path

import requests

from pipeline import registry

_HEADERS = {"User-Agent": "GT-Summer-Tracker/1.0 (unofficial fan project)"}


def photo_targets(players, leagues):
    out = []
    for p in players:
        summer = p["summer"]
        if summer.get("status") != "assigned":
            continue
        cfg = leagues.get(summer.get("league"), {})
        sid = str(summer.get("stats_id", ""))
        if cfg.get("platform") == "scorebook" and sid.isdigit():
            out.append((p["slug"], f"{cfg['api_base']}/player/{sid}"))
    return out


def main():
    players, leagues = registry.load_all("pipeline/players.yaml", "pipeline/leagues.yaml")
    dest = Path("site/public/headshots")
    dest.mkdir(parents=True, exist_ok=True)
    for slug, url in photo_targets(players, leagues):
        payload = requests.get(url, headers=_HEADERS, timeout=30).json()
        photo_url = (payload.get("player") or {}).get("photo")
        if not photo_url:
            print(f"{slug}: no photo on platform", file=sys.stderr)
            continue
        img = requests.get(photo_url, headers=_HEADERS, timeout=30)
        img.raise_for_status()
        (dest / f"{slug}.jpg").write_bytes(img.content)
        print(f"{slug}: saved -> add to players.yaml:  photo: /headshots/{slug}.jpg")
        time.sleep(1)


if __name__ == "__main__":
    main()

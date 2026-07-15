"""One-time GT athletics headshot fetcher.

Downloads official Georgia Tech headshots for all "returning" players in
players.yaml from the ramblinwreck.com baseball roster page into
site/public/headshots/{slug}.jpg (overwriting any existing photo, since
GT roster imagery is preferred over other sources for returning players).

The roster page is server-rendered; each player's headshot is an
`<img src="..." title="{Full Name}" alt="{Full Name}" class="sr-only">`
tag pointing at an imgproxy URL of the form
`.../imgproxy/{hash}/fit/2500/2500/ce/0/{base64-source}.jpg`. imgproxy
signs each URL for the specific size baked into the page, so requesting
a smaller `/fit/400/400/` variant of the same hash is rejected with a
403 ("Invalid signature"). This fetcher tries the smaller variant first
(in case a given URL isn't signature-locked) and falls back to
downloading the full 2500x2500 original + downscaling locally with
macOS `sips` when it isn't.

Usage: .venv/bin/python -m pipeline.fetch_gt_photos
"""
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

from pipeline import registry

_HEADERS = {"User-Agent": "GT-Summer-Tracker/1.0 (unofficial fan project)"}
_ROSTER_URL = "https://ramblinwreck.com/sports/m-basebl/roster/"
_DEST_DIR = Path("site/public/headshots")


def find_photo_url(html, full_name):
    """Locate the roster headshot <img> src for an exact player name."""
    pattern = r'<img src="([^"]+)" title="{name}" alt="{name}" class="sr-only">'.format(
        name=re.escape(full_name)
    )
    m = re.search(pattern, html)
    return m.group(1) if m else None


def small_variant(url):
    return url.replace("/fit/2500/2500/", "/fit/400/400/", 1)


def try_download(url, dest):
    """Attempt to save `url` to `dest`. Returns True on a valid image save."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
    except requests.RequestException:
        return False
    if resp.status_code != 200:
        return False
    if "image" not in resp.headers.get("Content-Type", ""):
        return False
    dest.write_bytes(resp.content)
    return True


def fetch_one(slug, full_name, html):
    photo_url = find_photo_url(html, full_name)
    if not photo_url:
        print(f"{slug}: could not locate a headshot for {full_name!r} on the roster page", file=sys.stderr)
        return None

    dest = _DEST_DIR / f"{slug}.jpg"

    small_url = small_variant(photo_url)
    if try_download(small_url, dest):
        time.sleep(1)
        return "small (400x400 imgproxy variant)"

    time.sleep(1)

    if try_download(photo_url, dest):
        subprocess.run(["sips", "-Z", "400", str(dest)], check=True, capture_output=True)
        time.sleep(1)
        return "full (2500x2500, downscaled with sips)"

    print(f"{slug}: headshot URL found but download failed for {full_name!r}", file=sys.stderr)
    return None


def main():
    players, _ = registry.load_all("pipeline/players.yaml", "pipeline/leagues.yaml")
    targets = [(p["slug"], p["name"]) for p in players if p.get("gt_status") == "returning"]

    print(f"Fetching roster page: {_ROSTER_URL}")
    resp = requests.get(_ROSTER_URL, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    _DEST_DIR.mkdir(parents=True, exist_ok=True)

    saved, skipped = [], []
    for slug, full_name in targets:
        strategy = fetch_one(slug, full_name, html)
        if strategy is None:
            skipped.append(slug)
            continue
        dest = _DEST_DIR / f"{slug}.jpg"
        size_kb = dest.stat().st_size / 1024
        print(f"{slug}: saved via {strategy} ({size_kb:.1f} KB) -> {dest}")
        saved.append(slug)

    print()
    print(f"Done: {len(saved)} saved, {len(skipped)} skipped")
    if skipped:
        print("Skipped players:", ", ".join(skipped))


if __name__ == "__main__":
    main()

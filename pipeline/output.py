"""Assemble site-facing player records and write the JSON contract + history."""
import json
import shutil
import sys
from pathlib import Path


def assemble(players, leagues, league_bundles, previous, today):
    records = []
    for p in players:
        summer_src = p["summer"]
        rec = {
            "slug": p["slug"], "name": p["name"], "gtStatus": p["gt_status"],
            "position": p.get("position", ""),
            "classYear": p.get("class2027") or "",
            "recruit": p.get("recruit") or None,
            "playerType": p.get("player_type"),
            "summer": {"status": summer_src["status"]},
            "photo": p.get("photo") or None,
            "asOf": None, "hitting": None, "pitching": None,
        }
        if summer_src["status"] == "assigned":
            rec["summer"]["team"] = summer_src["team"]
            rec["summer"]["leagueKey"] = summer_src["league"]
            bundle = league_bundles.get(summer_src["league"], {}).get(summer_src["stats_id"])
            if bundle:
                rec["hitting"], rec["pitching"] = bundle["hitting"], bundle["pitching"]
                rec["asOf"] = today
            else:
                prev = previous.get(p["slug"])
                if prev:  # league failed or scraper pending -> carry forward
                    rec["hitting"] = prev.get("hitting")
                    rec["pitching"] = prev.get("pitching")
                    rec["asOf"] = prev.get("asOf")
        records.append(rec)
    return records


def write_outputs(records, leagues, gamelogs_by_slug, out_dir, history_dir, today):
    out = Path(out_dir)
    (out / "gamelogs").mkdir(parents=True, exist_ok=True)

    (out / "players.json").write_text(json.dumps(records, indent=1))

    league_list = []
    for key, cfg in leagues.items():
        gt = [r["slug"] for r in records if r["summer"].get("leagueKey") == key]
        if gt:
            league_list.append({"key": key, "name": cfg["name"], "abbrev": cfg["abbrev"],
                                "officialUrl": cfg["official_url"],
                                "platform": cfg["platform"], "tier": cfg["tier"],
                                "gtPlayers": sorted(gt)})
    league_list.sort(key=lambda l: -len(l["gtPlayers"]))
    (out / "leagues.json").write_text(json.dumps(league_list, indent=1))

    for slug, log in gamelogs_by_slug.items():
        newest_first = sorted(log, key=lambda g: g["date"], reverse=True)
        (out / "gamelogs" / f"{slug}.json").write_text(json.dumps(newest_first, indent=1))

    snap = Path(history_dir) / today
    if snap.exists():
        shutil.rmtree(snap)
    shutil.copytree(out, snap)


def load_previous(out_dir):
    path = Path(out_dir) / "players.json"
    if not path.exists():
        return {}
    try:
        return {r["slug"]: r for r in json.loads(path.read_text())}
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
        print(f"[output] WARNING: previous players.json unreadable ({e}); starting fresh",
              file=sys.stderr)
        return {}

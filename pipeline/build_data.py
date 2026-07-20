"""Orchestrator: registry -> scrape -> validate -> compute -> write. CLI entry."""
import argparse
import datetime
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pipeline import compute, draft_registry, draft_status, name_watch, output, registry, validate
from pipeline.scrapers import SCRAPERS

DEFAULT_DRAFT_PATH = "pipeline/draft.yaml"


@dataclass
class BuildResult:
    failures: list = field(default_factory=list)   # (league_key, str(exception))
    skipped: list = field(default_factory=list)    # league keys with no scraper
    warnings: list = field(default_factory=list)


class ValidationFailure(Exception):
    pass


def build(players_path, leagues_path, out_dir, history_dir, today=None, draft_path=None):
    today = today or datetime.date.today().isoformat()
    draft_path = draft_path or DEFAULT_DRAFT_PATH
    players, leagues = registry.load_all(players_path, leagues_path)
    previous = output.load_previous(out_dir)
    result = BuildResult()
    league_bundles, gamelogs_by_slug = {}, {}

    for key, cfg in leagues.items():
        assigned = [p for p in players
                    if p["summer"]["status"] == "assigned" and p["summer"].get("league") == key]
        if not assigned:
            continue
        mod = SCRAPERS.get(cfg["platform"])
        if mod is None:
            result.skipped.append(key)
            print(f"[build] {key}: platform {cfg['platform']!r} has no scraper yet, skipping")
            continue
        try:
            stats = mod.fetch_league_stats(cfg)
            nw_warnings = name_watch.check_names(key, stats, players)
            result.warnings.extend(nw_warnings)
            for w in nw_warnings:
                print(f"[build] WARNING {w}")
            sids = [p["summer"]["stats_id"] for p in assigned]
            logs = mod.fetch_game_logs(cfg, sids)
            errors, warnings = validate.check_league(key, stats, assigned, previous)
            result.warnings.extend(warnings)
            for w in warnings:
                print(f"[build] WARNING {w}")
            if errors:
                raise ValidationFailure("; ".join(errors))
            league_bundles[key] = compute.league_bundle(cfg, stats, logs, wanted=set(sids))
            for p in assigned:
                sid = p["summer"]["stats_id"]
                if sid in league_bundles[key] and logs.get(sid):
                    gamelogs_by_slug[p["slug"]] = logs[sid]
        except Exception as e:  # noqa: BLE001 — per-league isolation is the point
            result.failures.append((key, str(e)))
            print(f"[build] FAILED {key}: {e} — keeping previous data (if any)", file=sys.stderr)

    if os.path.exists(draft_path):
        try:
            d_entries = draft_registry.load_draft(draft_path, {p["slug"] for p in players})
            draft_json = draft_status.build_draft(d_entries, today)
            os.makedirs(out_dir, exist_ok=True)
            # json.dumps serializes fully before the file is touched, so a bad payload
            # can't clobber the previous draft.json. History snapshot comes from
            # write_outputs' copytree of out_dir below.
            Path(out_dir, "draft.json").write_text(json.dumps(draft_json, indent=1))
        except Exception as e:  # noqa: BLE001 — same isolation ethos as leagues
            result.failures.append(("draft", str(e)))
            print(f"[build] FAILED draft: {e} — keeping previous data (if any)", file=sys.stderr)

    records = output.assemble(players, leagues, league_bundles, previous, today)
    output.write_outputs(records, leagues, gamelogs_by_slug, out_dir, history_dir, today)
    print(f"[build] wrote {len(records)} players; "
          f"{len(result.failures)} league failure(s), {len(result.skipped)} skipped, "
          f"{len(result.warnings)} warning(s)")
    return result


def main():
    ap = argparse.ArgumentParser(description="Build GT Summer Tracker data")
    ap.add_argument("--players", default="pipeline/players.yaml")
    ap.add_argument("--leagues", default="pipeline/leagues.yaml")
    ap.add_argument("--out", default="site/src/data")
    ap.add_argument("--history", default="data/history")
    ap.add_argument("--draft", default=None)
    args = ap.parse_args()
    result = build(args.players, args.leagues, args.out, args.history, draft_path=args.draft)
    sys.exit(1 if result.failures else 0)


if __name__ == "__main__":
    main()

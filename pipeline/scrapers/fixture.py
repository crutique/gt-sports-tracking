"""Scraper platform that reads canonical JSON from a directory.

Serves three purposes: test harness for the pipeline, stand-in data source for
leagues whose real scraper isn't written yet, and reference for the canonical
format every real platform scraper must normalize to.
"""
import json
from pathlib import Path


def fetch_league_stats(league_cfg):
    d = Path(league_cfg["fixture_dir"])
    return {
        "batting": json.loads((d / "batting.json").read_text()),
        "pitching": json.loads((d / "pitching.json").read_text()),
    }


def fetch_game_logs(league_cfg, stats_ids):
    d = Path(league_cfg["fixture_dir"])
    all_logs = json.loads((d / "gamelogs.json").read_text())
    return {sid: all_logs.get(sid, []) for sid in stats_ids}

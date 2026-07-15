"""Name watch: flag registry player names sitting in fetched league pools.

The pipeline fetches FULL league tables for percentile pools but only tracks
players assigned a stats_id in that league. A GT player can therefore sit in a
fetched pool for weeks while the registry still says "unassigned" and nobody
notices (Stroman/Walsh, July 2026). This module compares every fetched row's
name against the whole registry and emits warnings for any match that isn't
backed by a same-league, same-stats_id assignment.
"""


def _norm(name):
    """Normalize a name: lowercase, strip periods, collapse whitespace."""
    return " ".join(str(name).replace(".", "").split()).lower()


def check_names(league_key, tables, players):
    """Return warning strings for registry names found in fetched pools.

    Pure function. `tables` is {"batting": [rows], "pitching": [rows]} in the
    canonical scraper format (rows carry stats_id/name/team); `players` is the
    parsed players.yaml list. Matching is exact normalized full-name equality
    only — no substring/surname matching.
    """
    by_name = {}
    for p in players:
        by_name.setdefault(_norm(p.get("name", "")), []).append(p)

    warnings = []
    for side in ("batting", "pitching"):
        for row in tables.get(side) or []:
            row_name = row.get("name")
            if not row_name:
                continue
            for p in by_name.get(_norm(row_name), ()):
                summer = p.get("summer") or {}
                status = summer.get("status")
                assigned_here = (status == "assigned"
                                 and summer.get("league") == league_key)
                if assigned_here and str(summer.get("stats_id")) == str(row.get("stats_id")):
                    continue  # expected case: tracked player in their own pool
                if assigned_here:
                    registry_desc = (f"assigned to {league_key} "
                                     f"stats_id={summer.get('stats_id')}")
                    reason = "stats_id mismatch"
                elif status == "assigned":
                    registry_desc = f"assigned to {summer.get('league')}"
                    reason = "possible missing assignment"
                else:
                    registry_desc = status or "unknown"
                    reason = "possible missing assignment"
                warnings.append(
                    f"name-watch: '{p['name']}' (registry: {registry_desc}) matches "
                    f"{league_key} {side} row stats_id={row.get('stats_id')} "
                    f"team='{row.get('team', '')}' — {reason}")
    return warnings

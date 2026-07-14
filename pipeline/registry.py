"""Load and validate players.yaml + leagues.yaml."""
import yaml

VALID_GT_STATUS = {"returning", "transfer", "freshman"}
VALID_SUMMER_STATUS = {"assigned", "unassigned", "not_playing"}
VALID_PLAYER_TYPE = {"hitter", "pitcher", "two_way"}


class RegistryError(ValueError):
    pass


def load_all(players_path, leagues_path):
    with open(leagues_path) as f:
        leagues = yaml.safe_load(f) or {}
    with open(players_path) as f:
        players = yaml.safe_load(f) or []

    seen = set()
    for p in players:
        slug = p.get("slug")
        if not slug or not p.get("name"):
            raise RegistryError(f"player missing name/slug: {p!r}")
        if slug in seen:
            raise RegistryError(f"duplicate slug: {slug}")
        seen.add(slug)
        if p.get("gt_status") not in VALID_GT_STATUS:
            raise RegistryError(f"{slug}: bad gt_status {p.get('gt_status')!r}")
        summer = p.get("summer") or {}
        if summer.get("status") not in VALID_SUMMER_STATUS:
            raise RegistryError(f"{slug}: bad summer.status {summer.get('status')!r}")
        if summer["status"] == "assigned":
            if summer.get("league") not in leagues:
                raise RegistryError(f"{slug}: unknown league {summer.get('league')!r}")
            if p.get("player_type") not in VALID_PLAYER_TYPE:
                raise RegistryError(f"{slug}: assigned player needs player_type")
            if not summer.get("stats_id") or not summer.get("team"):
                raise RegistryError(f"{slug}: assigned player needs team and stats_id")
    return players, leagues

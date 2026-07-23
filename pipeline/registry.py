"""Load and validate players.yaml + leagues.yaml."""
import yaml

VALID_GT_STATUS = {"returning", "transfer", "freshman"}
VALID_SUMMER_STATUS = {"assigned", "unassigned", "not_playing"}
VALID_PLAYER_TYPE = {"hitter", "pitcher", "two_way"}
REQUIRED_LEAGUE_KEYS = ("name", "abbrev", "official_url", "platform", "tier")


class RegistryError(ValueError):
    pass


def load_all(players_path, leagues_path):
    with open(leagues_path) as f:
        leagues = yaml.safe_load(f) or {}
    with open(players_path) as f:
        players = yaml.safe_load(f) or []

    for league_id, cfg in leagues.items():
        cfg = cfg or {}
        for key in REQUIRED_LEAGUE_KEYS:
            if key not in cfg:
                raise RegistryError(f"{league_id}: league {key} missing")
        if cfg["platform"] == "fixture" and "fixture_dir" not in cfg:
            raise RegistryError(f"{league_id}: league fixture_dir missing")

    seen = set()
    seen_stats_ids = {}
    for p in players:
        slug = p.get("slug")
        if not slug or not p.get("name"):
            raise RegistryError(f"player missing name/slug: {p!r}")
        if slug in seen:
            raise RegistryError(f"duplicate slug: {slug}")
        seen.add(slug)
        if p.get("gt_status") not in VALID_GT_STATUS:
            raise RegistryError(f"{slug}: bad gt_status {p.get('gt_status')!r}")
        if p.get("gt_status") == "transfer" and not p.get("from_school"):
            raise RegistryError(f"{slug}: transfer needs from_school")
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
            league = summer["league"]
            stats_id = summer["stats_id"]
            league_stats_ids = seen_stats_ids.setdefault(league, set())
            if stats_id in league_stats_ids:
                raise RegistryError(
                    f"{slug}: duplicate stats_id {stats_id!r} in league {league}"
                )
            league_stats_ids.add(stats_id)
    return players, leagues

"""Load and validate pipeline/draft.yaml (the 2026 MLB draft class)."""
import yaml

from pipeline.registry import RegistryError

VALID_GT_ROLE = {"departing", "signee"}


def load_draft(path, player_slugs):
    """player_slugs: set of slugs from players.yaml, for cross-linking validation."""
    with open(path) as f:
        entries = yaml.safe_load(f) or []
    seen = set()
    for e in entries:
        name = e.get("name")
        if not name:
            raise RegistryError(f"draft entry missing name: {e!r}")
        if name in seen:
            raise RegistryError(f"draft: duplicate name {name!r}")
        seen.add(name)
        if e.get("gt_role") not in VALID_GT_ROLE:
            raise RegistryError(f"draft: {name}: bad gt_role {e.get('gt_role')!r}")
        udfa = e.get("udfa")
        if udfa is not None:
            if not udfa.get("team"):
                raise RegistryError(f"draft: {name}: udfa entry needs team")
        elif not isinstance(e.get("person_id"), int):
            raise RegistryError(f"draft: {name}: needs numeric person_id (or udfa block)")
        rep = e.get("reported")
        if rep is not None and not (rep.get("bonus") and rep.get("source")):
            raise RegistryError(f"draft: {name}: reported needs bonus and source")
        slug = e.get("slug")
        if slug and slug not in player_slugs:
            raise RegistryError(f"draft: {name}: slug {slug!r} not in players registry")
    return entries

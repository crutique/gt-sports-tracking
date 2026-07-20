"""Load and validate pipeline/draft.yaml (the 2026 MLB draft class)."""
import yaml

from pipeline.registry import RegistryError

VALID_GT_ROLE = {"departing", "signee"}


def load_draft(path, player_slugs):
    """player_slugs: set of slugs from players.yaml, for cross-linking validation."""
    with open(path) as f:
        entries = yaml.safe_load(f) or []
    seen = set()
    seen_person_ids = set()
    seen_slugs = set()
    for e in entries:
        if not isinstance(e, dict):
            raise RegistryError(f"draft: entry must be a mapping: {e!r}")
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
        person_id = e.get("person_id")
        if person_id is not None:
            if person_id in seen_person_ids:
                raise RegistryError(f"draft: {name}: duplicate person_id {person_id!r}")
            seen_person_ids.add(person_id)
        returning = e.get("returning")
        if returning is not None and not isinstance(returning, bool):
            raise RegistryError(f"draft: {name}: returning must be a bool")
        rep = e.get("reported")
        if rep is not None:
            if not (rep.get("bonus") and rep.get("source")):
                raise RegistryError(f"draft: {name}: reported needs bonus and source")
            if not isinstance(rep["bonus"], int):
                raise RegistryError(f"draft: {name}: reported bonus must be an int")
        unv = e.get("unverified")
        if unv is not None and not (isinstance(unv.get("bonus"), int)
                                    and unv.get("source") and unv.get("detected")):
            raise RegistryError(f"draft: {name}: unverified needs int bonus, source, detected")
        slug = e.get("slug")
        if slug:
            if slug in seen_slugs:
                raise RegistryError(f"draft: {name}: duplicate slug {slug!r}")
            seen_slugs.add(slug)
            if slug not in player_slugs:
                raise RegistryError(f"draft: {name}: slug {slug!r} not in players registry")
    return entries

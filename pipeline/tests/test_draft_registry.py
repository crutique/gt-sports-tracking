import pytest
from pipeline import draft_registry
from pipeline.registry import RegistryError

SLUGS = {"isaiah-galason"}


def _write(tmp_path, text):
    p = tmp_path / "draft.yaml"
    p.write_text(text)
    return str(p)


def test_load_seed_file():
    entries = draft_registry.load_draft("pipeline/draft.yaml", SLUGS)
    names = [e["name"] for e in entries]
    assert "Vahn Lackey" in names and "Isaiah Galason" in names
    galason = next(e for e in entries if e["name"] == "Isaiah Galason")
    assert galason["gt_role"] == "signee" and galason["slug"] == "isaiah-galason"


def test_duplicate_name_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing}\n"
                            "- {name: A, person_id: 2, gt_role: departing}\n")
    with pytest.raises(RegistryError, match="duplicate"):
        draft_registry.load_draft(path, set())


def test_bad_gt_role_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: alumni}\n")
    with pytest.raises(RegistryError, match="gt_role"):
        draft_registry.load_draft(path, set())


def test_non_udfa_needs_numeric_person_id(tmp_path):
    path = _write(tmp_path, "- {name: A, gt_role: departing}\n")
    with pytest.raises(RegistryError, match="person_id"):
        draft_registry.load_draft(path, set())


def test_udfa_needs_team(tmp_path):
    path = _write(tmp_path, "- {name: A, gt_role: departing, udfa: {date: '2026-07-15'}}\n")
    with pytest.raises(RegistryError, match="udfa"):
        draft_registry.load_draft(path, set())


def test_reported_needs_bonus_and_source(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing, reported: {bonus: 100}}\n")
    with pytest.raises(RegistryError, match="reported"):
        draft_registry.load_draft(path, set())


def test_unknown_slug_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: signee, slug: nobody}\n")
    with pytest.raises(RegistryError, match="slug"):
        draft_registry.load_draft(path, {"someone-else"})

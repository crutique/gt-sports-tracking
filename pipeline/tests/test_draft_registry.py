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


def test_non_dict_entry_rejected(tmp_path):
    path = _write(tmp_path, "- Vahn Lackey\n")
    with pytest.raises(RegistryError, match="mapping"):
        draft_registry.load_draft(path, set())


def test_missing_name_rejected(tmp_path):
    path = _write(tmp_path, "- {person_id: 1, gt_role: departing}\n")
    with pytest.raises(RegistryError, match="name"):
        draft_registry.load_draft(path, set())


def test_duplicate_person_id_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing}\n"
                            "- {name: B, person_id: 1, gt_role: departing}\n")
    with pytest.raises(RegistryError, match="duplicate"):
        draft_registry.load_draft(path, set())


def test_duplicate_slug_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: signee, slug: s}\n"
                            "- {name: B, person_id: 2, gt_role: signee, slug: s}\n")
    with pytest.raises(RegistryError, match="duplicate"):
        draft_registry.load_draft(path, {"s"})


def test_non_bool_returning_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing, returning: yep}\n")
    with pytest.raises(RegistryError, match="returning"):
        draft_registry.load_draft(path, set())


def test_non_int_reported_bonus_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing,"
                            " reported: {bonus: lots, source: s}}\n")
    with pytest.raises(RegistryError, match="reported"):
        draft_registry.load_draft(path, set())


def test_unverified_block_valid(tmp_path):
    path = _write(tmp_path, '- {name: A, person_id: 1, gt_role: departing, '
                            'unverified: {bonus: 1900000, source: "https://x", detected: "2026-07-21"}}\n')
    assert draft_registry.load_draft(path, set())[0]["unverified"]["bonus"] == 1900000


def test_unverified_requires_all_fields(tmp_path):
    path = _write(tmp_path, '- {name: A, person_id: 1, gt_role: departing, '
                            'unverified: {bonus: 1900000, source: "https://x"}}\n')
    with pytest.raises(RegistryError, match="unverified"):
        draft_registry.load_draft(path, set())


def test_unverified_bonus_must_be_int(tmp_path):
    path = _write(tmp_path, '- {name: A, person_id: 1, gt_role: departing, '
                            'unverified: {bonus: "1.9M", source: "https://x", detected: "2026-07-21"}}\n')
    with pytest.raises(RegistryError, match="unverified"):
        draft_registry.load_draft(path, set())

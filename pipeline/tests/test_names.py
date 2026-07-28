"""Name canonicalisation -- every case here came from real crawled data.

The first 2023-2026 crawl produced 1,553 schools and 184 people on one roster,
because scorers spell the same entity several ways within a single season. These
tests pin the specific collisions that caused it.
"""
from pipeline.names import canon_person, canon_school, display_name, split_person


# --- schools ----------------------------------------------------------------
def test_abbreviated_state_names_merge():
    for short, long in [("Western Mich.", "Western Michigan"),
                        ("Central Mich.", "Central Michigan"),
                        ("Eastern Mich.", "Eastern Michigan"),
                        ("South Fla.", "South Florida"),
                        ("Ga. Southern", "Georgia Southern"),
                        ("Col. of Charleston", "College of Charleston")]:
        assert canon_school(short) == canon_school(long), f"{short} != {long}"


def test_trailing_st_is_state_and_leading_st_is_saint():
    assert canon_school("Penn St.") == canon_school("Penn State")
    assert canon_school("Ohio St.") == canon_school("Ohio State")
    # the trap: "St. John's" is Saint, and must not become "statejohns"
    assert canon_school("St. John's") == canon_school("Saint John's")
    assert canon_school("St. Michael's") == canon_school("Saint Michael's")
    assert canon_school("St. John's") != canon_school("State John's")


def test_distinct_schools_stay_distinct():
    """Aggressive normalising is worse than none -- these must never merge."""
    pairs = [("Michigan", "Michigan State"),
             ("Boston College", "Boston University"),
             ("Texas", "Texas A&M"),
             ("Miami (Fla.)", "Miami (Ohio)"),
             ("Georgia", "Georgia Tech"),
             ("Cal State Fullerton", "Cal State Northridge")]
    for a, b in pairs:
        assert canon_school(a) != canon_school(b), f"{a} merged into {b}"


def test_ampersand_and_punctuation_variants_merge():
    assert canon_school("Texas A&M") == canon_school("Texas A and M")
    assert canon_school("Miami (Fla.)") == canon_school("Miami Fla.")


def test_empty_input_is_empty():
    assert canon_school("") == "" and canon_school(None) == ""


# --- people -----------------------------------------------------------------
def test_name_order_and_truncation_collapse_to_one_person():
    """The real Advincula/Mally collisions that split their 2026 seasons."""
    advincula = {"Advincula, Jarren", "Jarren Advincula", "ADVINCULA, J.",
                 "Advincula,Jarren"}
    assert len({canon_person(n) for n in advincula}) == 1

    mally = {"MALLY, Tanner", "MALLY, T.", "Mally, Tanner", "Tanner Mally"}
    assert len({canon_person(n) for n in mally}) == 1


def test_different_people_sharing_a_surname_stay_apart():
    assert canon_person("Williams, Zack") != canon_person("Williams, Adam")


def test_generational_suffix_stays_with_the_surname():
    first, last = split_person("Anthony Pack Jr.")
    assert last == "Pack Jr." and first == "Anthony"
    assert canon_person("Anthony Pack Jr.") == canon_person("Pack Jr., Anthony")


def test_surname_only_is_still_keyed():
    assert canon_person("Vercollone") == "vercollone-"
    assert canon_person("Vercollone") != canon_person("Vercollone, Mike")


def test_display_name_normalises_order():
    assert display_name("Advincula, Jarren") == "Jarren Advincula"
    assert display_name("Jarren Advincula") == "Jarren Advincula"
    assert display_name("Vercollone") == "Vercollone"

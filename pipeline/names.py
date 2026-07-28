"""Canonicalising school and person names as scorers actually write them.

Every StatCrew file is typed by a human at a ballpark, and the same entity
arrives spelled several ways *within one season*. Left alone this fragments the
data silently: a first crawl of 2023-2026 produced **1,553 schools** (against
roughly 300 D1 programmes plus opponents) and **184 people on a single 2026
roster** (against a real roster of ~40). Season totals were split across the
fragments, so every rate stat was computed on a slice.

Two distinct problems, deliberately solved separately:

**Schools** differ by abbreviation -- ``Western Mich.`` / ``Western Michigan``,
``Central Caro.`` / ``Central Carolina``. The fix is expanding the AP-style
abbreviations scorers use, not fuzzy matching, which would happily merge
``Michigan`` with ``Michigan State``.

**People** differ by name order and truncation -- ``Advincula, Jarren`` /
``Jarren Advincula``, ``MALLY, Tanner`` / ``MALLY, T.`` / ``Mally, Tanner``. The
fix is a (surname, first-initial) key, because the first name is the part that
gets truncated and the surname is the part that does not.

**The `St.` trap.** ``St.`` means *State* in ``Penn St.`` and *Saint* in
``St. John's``. Position decides: trailing is State, leading is Saint. Getting
this backwards turned ``St. Michael's`` into ``statemichaels``.
"""
import re

#: AP-style abbreviations as they appear in scorer files and NCAA feeds.
_ABBR = {
    "ala": "alabama", "ariz": "arizona", "ark": "arkansas", "calif": "california",
    "colo": "colorado", "conn": "connecticut", "del": "delaware", "fla": "florida",
    "ga": "georgia", "ill": "illinois", "ind": "indiana", "ky": "kentucky",
    "la": "louisiana", "mass": "massachusetts", "md": "maryland", "mich": "michigan",
    "minn": "minnesota", "miss": "mississippi", "mo": "missouri", "mont": "montana",
    "neb": "nebraska", "nev": "nevada", "okla": "oklahoma", "ore": "oregon",
    "pa": "pennsylvania", "penn": "pennsylvania", "tenn": "tennessee",
    "tex": "texas", "va": "virginia", "vt": "vermont", "wash": "washington",
    "wis": "wisconsin", "wyo": "wyoming", "caro": "carolina", "car": "carolina",
    "cent": "central", "col": "college", "univ": "university", "intl": "international",
    "chr": "christian", "val": "valley", "st": "state",
}

_DROP = {"university", "the", "of", "at"}
_PUNCT = re.compile(r"[^a-z0-9]+")


def canon_school(name):
    """Normalised key for a school name.

    Expands abbreviations, resolves the ``St.`` ambiguity by position, and drops
    only genuinely meaningless words. ``College`` is **kept** -- ``Boston
    College`` and ``Boston University`` are different schools.
    """
    s = (name or "").strip()
    if not s:
        return ""
    s = s.replace("&", " and ")
    # leading "St." is Saint; anywhere else it is State
    s = re.sub(r"^St\.?\s+", "saint ", s, flags=re.I)
    s = s.lower()
    # parentheticals disambiguate rather than decorate: "Wayne St. (Mich.)"
    s = s.replace("(", " ").replace(")", " ")
    out = []
    for tok in re.split(r"[\s\-\./,']+", s):
        tok = tok.strip(".")
        if not tok or tok in _DROP:
            continue
        out.append(_ABBR.get(tok, tok))
    return _PUNCT.sub("", "".join(out))


def split_person(name):
    """``(first, last)`` from any order a scorer might type.

    Handles ``'Advincula, Jarren'``, ``'Jarren Advincula'``, ``'MALLY, T.'`` and
    bare ``'Vercollone'``. Suffixes are kept with the surname so ``Pack Jr.``
    does not resolve to the surname ``Jr``.
    """
    s = re.sub(r"\s+", " ", (name or "").strip())
    if not s:
        return "", ""
    if "," in s:
        last, _, first = s.partition(",")
        return first.strip(), last.strip()
    parts = s.split(" ")
    if len(parts) == 1:
        return "", parts[0]
    # trailing generational suffix belongs to the surname
    if len(parts) > 2 and re.fullmatch(r"(?i)(jr|sr|ii|iii|iv)\.?", parts[-1]):
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    return " ".join(parts[:-1]), parts[-1]


def canon_person(name):
    """Match key for a person: surname plus first initial.

    The first name is what gets truncated (``Tanner`` -> ``T.``), the surname is
    what survives, so the initial is the most information that can be relied on.
    Two players on one roster sharing both a surname and an initial will merge --
    rare, and preferable to splitting one player's season into three rows.
    """
    first, last = split_person(name)
    last_key = _PUNCT.sub("", last.lower())
    first_key = _PUNCT.sub("", first.lower())[:1]
    return f"{last_key}-{first_key}" if last_key else ""


def display_name(name):
    """``'Advincula, Jarren'`` -> ``'Jarren Advincula'``; leave other forms be."""
    first, last = split_person(name)
    return f"{first} {last}".strip() if first else last

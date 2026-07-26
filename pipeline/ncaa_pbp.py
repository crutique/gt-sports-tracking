"""Extract the events NCAA box scores omit — HBP, SF, SH — from play-by-play text.

Division of labour, by design: the box score is *structured* data and stays the
authority for AB/R/H/RBI/BB/K/2B/3B/HR (no text parsing, no ambiguity). Its schema
simply has no hit-by-pitch or sacrifice fields, and those are required for exact
OBP/OPS/wOBA. Play-by-play carries them, so this module reads PBP for **only**
those three events and attributes each to a player on that half-inning's batting
roster (supplied from the same game's box score).

Grammar notes, derived from 1,822 real plays across 24 games (2026 season) rather
than assumed:

- Clauses are separated by ``;`` **and** by a literal ``3a`` — the feed's separator
  (0x3a) arrives with its escape prefix stripped, e.g.
  ``"FORD, H. singled to left field (1-2 BFK)3a CHAPMAN, R. advanced to second."``
- Trailing ``(1-2 KFB)`` is the ball-strike count + pitch sequence, never content.
- Hit by pitch is always ``"<name> hit by pitch"``.
- Sacrifice flies appear three ways: ``", SF, RBI"``, ``", sacrifice fly, RBI"``,
  and the leading ``"<name> sacrifice fly to left center putout by lf, RBI"``.
  A fly out that merely drives in a run is NOT an SF unless the feed marks it.
- Scorer software differs per school, so names arrive as ``Fralick, C.`` /
  ``Murphy,Preston`` / ``Davis Hanson`` / ``Z. Williams`` / bare ``Vercollone``.
  Hence roster matching rather than name parsing — and when a name is genuinely
  ambiguous (two ``Williams``), the event is left unattributed instead of guessed.
"""
import re
import unicodedata

HBP = "hbp"
SF = "sf"
SH = "sh"

# clause separators: ';' or the mangled '3a' (only when it delimits, i.e. is
# followed by whitespace — so it never splits a token that happens to contain it)
_SPLIT = re.compile(r";\s*|3a(?=\s)")
# trailing/embedded count + pitch sequence: "(1-2 KFB)", "(3-1)", "(0-0 B)"
_COUNT = re.compile(r"\s*\(\d+-\d+[^)]*\)")

_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def split_clauses(text):
    """Split a play into its clauses, stripping counts and trailing punctuation."""
    out = []
    for part in _SPLIT.split(text or ""):
        part = _COUNT.sub("", part).strip().rstrip(".").strip()
        if part:
            out.append(part)
    return out


def classify(clause):
    """Return HBP / SF / SH for a batter-event clause, else None."""
    low = clause.lower()
    if "hit by pitch" in low:
        return HBP
    # SF: explicit marker only — ", SF," / "sacrifice fly" (never a bare RBI flyout)
    if re.search(r",\s*sf\b", low) or "sacrifice fly" in low or "sac fly" in low:
        return SF
    if "sacrifice bunt" in low or "sacrificed" in low or re.search(r",\s*sh\b", low):
        return SH
    return None


def leading_name(clause):
    """The player name at the head of a clause, before the action verb."""
    clause = _COUNT.sub("", clause).strip()
    # "Last, First"/"Last, C." keeps its comma; "Last,First" has no space.
    m = re.match(r"^([A-Z][\w'\-]*,\s?[A-Z][\w'\-]*\.?)", clause)
    if m:
        return m.group(1).strip()
    # otherwise take words until the action verb starts
    words = clause.split()
    taken = []
    for w in words:
        bare = w.strip(".,").lower()
        if taken and not (w[:1].isupper() or bare in _SUFFIXES):
            break
        taken.append(w)
        if len(taken) >= 3:
            break
    return " ".join(taken).rstrip(",").strip()


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def _name_parts(name):
    """(last, first) as normalized strings; first may be a single initial or ''."""
    name = _COUNT.sub("", name).strip().rstrip(".")
    if "," in name:
        last, _, first = name.partition(",")
        return _norm(last), _norm(first)
    words = [w for w in name.split() if _norm(w) and _norm(w) not in _SUFFIXES]
    if len(words) >= 2:
        # "Z. Williams" -> initial first; "Davis Hanson" -> first last
        if words[0].rstrip(".").isalpha() and len(words[0].rstrip(".")) == 1:
            return _norm(words[-1]), _norm(words[0])
        return _norm(words[-1]), _norm(words[0])
    return (_norm(words[0]) if words else ""), ""


def _consistent(a, b):
    """Two first-name forms agree if equal or one is the other's initial."""
    if not a or not b:
        return True
    if a == b:
        return True
    return a[0] == b[0] and (len(a) == 1 or len(b) == 1)


def match_player(name, roster):
    """Match a PBP name to a roster entry's ``key``. None if unknown or ambiguous."""
    last, first = _name_parts(name)
    if not last:
        return None
    cands = [p for p in roster if _norm(p.get("lastName")) == last]
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]["key"]
    narrowed = [p for p in cands if _consistent(first, _norm(p.get("firstName")))]
    # refuse to guess between real people
    return narrowed[0]["key"] if len(narrowed) == 1 else None


def game_events(pbp_payload, rosters):
    """``{team_id: {player_key: {hbp,sf,sh}}}`` for one game.

    ``rosters`` maps team_id -> [{key, firstName, lastName}, ...] (from the box
    score). Only the clause's *batter* is credited; later clauses in the same play
    describe baserunners and carry no batter event.
    """
    out = {}
    for period in pbp_payload.get("periods") or []:
        for half in period.get("playbyplayStats") or []:
            team_id = half.get("teamId")
            roster = rosters.get(team_id)
            if not roster:
                continue
            for play in half.get("plays") or []:
                for clause in split_clauses(play.get("playText")):
                    kind = classify(clause)
                    if not kind:
                        continue
                    key = match_player(leading_name(clause), roster)
                    if key is None:
                        continue
                    tally = out.setdefault(team_id, {}).setdefault(
                        key, {HBP: 0, SF: 0, SH: 0})
                    tally[kind] += 1
    return out


def split_packed_name(first, last):
    """Normalize a box-score name to ``(first, last)``.

    Roughly one game in twelve arrives with ``firstName`` empty and the whole name
    packed into ``lastName`` ("Vahn Lackey"). Left alone that mints a second
    identity for the same player — it silently split players' seasons in two
    during validation — and it also breaks surname matching against play text.
    """
    first, last = (first or "").strip(), (last or "").strip()
    if first or " " not in last:
        return first, last
    words = last.split()
    # drop a trailing generational suffix so the surname is the real surname
    if len(words) > 2 and words[-1].strip(".").lower() in _SUFFIXES:
        words = words[:-1]
    return " ".join(words[:-1]), words[-1]


def roster_from_boxscore(team_box):
    """Roster entries (key = 'first-last' slug) for players with a batting line."""
    roster = []
    for p in team_box.get("playerStats") or []:
        if not p.get("batterStats"):
            continue
        first, last = split_packed_name(p.get("firstName"), p.get("lastName"))
        roster.append({"key": f"{_norm(first)}-{_norm(last)}",
                       "firstName": first, "lastName": last})
    return roster

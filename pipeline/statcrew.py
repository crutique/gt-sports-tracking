"""Reader for StatCrew ``bsgame`` XML -- the scorer's own output.

This is the file the scoring software writes at the ballpark. Every other feed
this project touches (ncaa.com's gamecenter, ESPN, school and conference sites)
is a *rendering derived from it*, which is why going to the XML directly gets us
strictly more than any of them:

* **HBP / SF / SH are attributes**, not prose to be pattern-matched. The whole
  grammar in :mod:`pipeline.ncaa_pbp` -- three spellings of sacrifice fly, the
  literal ``3a`` clause separator, per-school scorer dialects -- is unnecessary
  for any game available here.
* **Batter strikeouts exist.** NCAA's JSON feed never fills them (0 of 395 real
  batting rows in a 2025 sample), so K% is not computable from that source at all.
* **Base-out state is explicit** -- ``outs`` plus named runners on ``first`` /
  ``second`` / ``third`` before each play -- so a Gameday view needs no inference.
* **Handedness** (``bats`` / ``throws``, and per-play ``batprof`` / ``pchprof``)
  comes free, which ESPN's feed does not carry at all.
* **Identity is given** -- full name, uniform number, position, class -- so the
  surname-collision guessing in :mod:`pipeline.ncaa_season` is not needed.

Two shape rules the format imposes, both load-bearing:

1. **A zero stat is an omitted attribute.** StatCrew writes only what happened,
   so a player with no walks simply has no ``bb=``. Readers must default missing
   to 0 or every line silently loses its zeros.
2. **Innings pitched are ``innings.outs``**, not a decimal -- ``0.2`` is two
   outs, ``1.1`` is four. Averaging or summing them as floats is wrong.

Canonical keys match the rest of the pipeline (:mod:`pipeline.stats_math`).
"""
import re
import xml.etree.ElementTree as ET

# <hitting> attribute -> canonical key. StatCrew omits zeros, so every one of
# these is defaulted rather than looked up.
_BAT = {"ab": "ab", "r": "r", "h": "h", "double": "d", "triple": "t", "hr": "hr",
        "rbi": "rbi", "bb": "bb", "so": "k", "hbp": "hbp", "sf": "sf", "sh": "sh",
        "sb": "sb", "cs": "cs", "gdp": "gdp", "kl": "kl"}
_PIT = {"h": "h", "r": "r", "er": "er", "bb": "bb", "so": "k", "hbp": "hb",
        "hr": "hr", "bf": "bf", "ab": "ab", "sfa": "sfa", "sha": "sha",
        "ibb": "ibb", "kl": "kl", "pitches": "pitches", "strikes": "strikes",
        "win": "w", "loss": "l", "gs": "gs", "appear": "g"}

# trailing "(3-2 BFKFFBBK)" on a narrative: balls-strikes then the pitch sequence
_COUNT = re.compile(r"\((\d)-(\d)(?:\s+([A-Za-z]+))?\)")


def _int(v):
    try:
        return int(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0


def ip_to_outs(ip):
    """``"8.0"`` -> 24, ``"0.2"`` -> 2. StatCrew IP is ``innings.outs``."""
    s = str(ip or "").strip()
    if not s:
        return 0
    whole, _, frac = s.partition(".")
    return _int(whole) * 3 + _int(frac)


def _line(el, mapping):
    """Canonical stat line from an element's attributes, zeros filled in."""
    if el is None:
        return None
    return {dst: _int(el.get(src)) for src, dst in mapping.items()}


def _batting(el):
    row = _line(el, _BAT)
    return row if row is not None else {v: 0 for v in _BAT.values()}


def _pitching(el):
    if el is None:
        return None
    row = _line(el, _PIT)
    row["ip_outs"] = ip_to_outs(el.get("ip"))
    return row


def _player(el):
    return {
        "name": el.get("name") or el.get("shortname") or "",
        "shortname": el.get("shortname") or "",
        "uni": el.get("uni") or "",
        "pos": el.get("pos") or "",
        "bats": el.get("bats") or "",
        "throws": el.get("throws") or "",
        "cls": el.get("class") or "",
        "gp": _int(el.get("gp")),
        "spot": _int(el.get("spot")),
        "batting": _batting(el.find("hitting")),
        "pitching": _pitching(el.find("pitching")),
    }


def _team(el):
    ls = el.find("linescore")
    totals = el.find("totals")
    return {
        "id": el.get("id") or "",
        "name": el.get("name") or "",
        "vh": el.get("vh") or "",
        "record": el.get("record") or "",
        "runs": _int(ls.get("runs")) if ls is not None else 0,
        "hits": _int(ls.get("hits")) if ls is not None else 0,
        "errs": _int(ls.get("errs")) if ls is not None else 0,
        "lob": _int(ls.get("lob")) if ls is not None else 0,
        "linescore": [_int(x) for x in (ls.get("line") or "").split(",") if x != ""]
                     if ls is not None else [],
        "players": [_player(p) for p in el.findall("player")],
        "totals": {
            "batting": _batting(totals.find("hitting") if totals is not None else None),
            "pitching": _pitching(totals.find("pitching") if totals is not None else None),
        },
    }


def _date(raw):
    """``"2/15/2026"`` -> ``"2026-02-15"``; pass anything unexpected through."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", str(raw or ""))
    if not m:
        return (raw or "").strip()
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _plays(root):
    out = []
    for inning in root.iter("inning"):
        num = _int(inning.get("number"))
        for half in inning.findall("batting"):
            for play in half.findall("play"):
                narrative = play.find("narrative")
                text = (narrative.get("text") if narrative is not None else "") or ""
                m = _COUNT.search(text)
                out.append({
                    "inning": num,
                    "half": half.get("vh") or "",
                    "teamId": half.get("id") or "",
                    "seq": _int(play.get("seq")),
                    "outs": _int(play.get("outs")),
                    "bases": {"first": play.get("first") or None,
                              "second": play.get("second") or None,
                              "third": play.get("third") or None},
                    "batter": play.get("batter") or "",
                    "batterHand": play.get("batprof") or "",
                    "pitcher": play.get("pitcher") or "",
                    "pitcherHand": play.get("pchprof") or "",
                    "text": text,
                    "count": {"balls": _int(m.group(1)), "strikes": _int(m.group(2))}
                             if m else {"balls": 0, "strikes": 0},
                    "pitches": (m.group(3) or "") if m else "",
                })
    return out


def parse_game(xml_text):
    """Parse one ``bsgame`` document into canonical dicts."""
    root = ET.fromstring(xml_text)
    venue = root.find("venue")
    v = venue.attrib if venue is not None else {}
    status = root.find("status")
    teams = [_team(t) for t in root.findall("team")]
    away = next((t for t in teams if t["vh"].upper() == "V"), teams[0] if teams else None)
    home = next((t for t in teams if t["vh"].upper() == "H"), teams[-1] if teams else None)
    return {
        "source": root.get("source") or "",
        "gameid": v.get("gameid") or "",
        "sbid": v.get("sbid") or "",
        "date": _date(v.get("date")),
        "start": v.get("start") or "",
        "location": v.get("location") or "",
        "stadium": v.get("stadium") or "",
        "attend": _int(v.get("attend")),
        "duration": v.get("duration") or "",
        # 9 for baseball, 7 for softball -- the only sport discriminator the
        # format carries, since both are scored into the same `bsgame` root.
        "sched_innings": _int(v.get("schedinn")),
        "leaguegame": (v.get("leaguegame") or "").upper() == "Y",
        "complete": (status.get("complete") or "").upper() == "Y"
                    if status is not None else False,
        "away": away,
        "home": home,
        "teams": teams,
        "plays": _plays(root),
    }

"""Merge MLB draft + transactions data with curated draft.yaml into draft.json."""
import requests

API = "https://statsapi.mlb.com/api/v1"
DEADLINE = "2026-07-27"    # ISO date; unsigned after this -> did_not_sign
_TIMEOUT = 30


def _get(url):
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _bonus(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def fetch_picks(year=2026):
    data = _get(f"{API}/draft/{year}")
    picks = {}
    for rd in data["drafts"]["rounds"]:
        for p in rd.get("picks", []):
            pid = (p.get("person") or {}).get("id")
            if pid:
                picks[pid] = {
                    "round": rd.get("round"), "pick": p.get("pickNumber"),
                    "team": (p.get("team") or {}).get("name"),
                    # pickValue/signingBonus come back as numeric strings from the
                    # live API (e.g. "9740100"), so both go through _bonus().
                    "slot": _bonus(p.get("pickValue")),
                    "officialBonus": _bonus(p.get("signingBonus")),
                    "headshot": p.get("headshotLink"),
                }
    return picks


def fetch_signing(person_id, today):
    """Earliest official SGN transaction date since the draft window opened, or None."""
    data = _get(f"{API}/transactions?playerId={person_id}"
                f"&startDate=2026-07-01&endDate={today}")
    dates = [t.get("date") for t in data.get("transactions", [])
             if t.get("typeCode") == "SGN" and t.get("date")]
    return min(dates) if dates else None


def _status(signed, returning, today, deadline):
    if signed:
        return "signed"
    if returning:
        return "returning"
    if today > deadline:
        return "did_not_sign"
    return "unsigned"


def build_draft(entries, today, deadline=DEADLINE):
    picks = fetch_picks()
    players, udfa = [], []
    for e in entries:
        if e.get("udfa"):
            u = e["udfa"]
            udfa.append({"name": e["name"], "personId": None, "gtRole": e["gt_role"],
                         "slug": e.get("slug"), "round": None, "pick": None,
                         "team": u["team"], "slot": None, "bonus": None,
                         "bonusSource": None, "reportedSourceUrl": u.get("source"),
                         "status": "signed_udfa", "signedDate": u.get("date"),
                         "headshot": None, "note": e.get("note")})
            continue
        pid = e["person_id"]
        pick = picks.get(pid) or {}
        signed_date = fetch_signing(pid, today)
        official = pick.get("officialBonus")
        rep = e.get("reported") or {}
        signed = bool(signed_date) or official is not None
        bonus, source, rep_url = None, None, None
        if official is not None:
            bonus, source = official, "official"
        elif rep.get("bonus"):
            bonus, source, rep_url = rep["bonus"], "reported", rep["source"]
        players.append({"name": e["name"], "personId": pid, "gtRole": e["gt_role"],
                        "slug": e.get("slug"), "round": pick.get("round"),
                        "pick": pick.get("pick"), "team": pick.get("team"),
                        "slot": pick.get("slot"), "bonus": bonus,
                        "bonusSource": source, "reportedSourceUrl": rep_url,
                        "status": _status(signed, bool(e.get("returning")), today, deadline),
                        "signedDate": signed_date, "headshot": pick.get("headshot"),
                        "note": e.get("note")})
    players.sort(key=lambda p: p["pick"] if p["pick"] is not None else 10**6)
    return {"asOf": today, "players": players, "udfa": udfa}

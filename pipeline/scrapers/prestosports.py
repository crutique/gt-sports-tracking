"""Scraper for PrestoSports-hosted league sites (server-rendered HTML tables).

League stats:  GET {site_base}/{sport_path}/{season}/players?pos={h|p}&sort=...&start=N
               Every page carries four stats tables — hitting, baserunning,
               pitching, fielding — for one slice of players. Tables are
               identified by their headers (never by position on the page) and
               rows are keyed on the player-page slug in each row's href.
               Batting rows merge the hitting + baserunning tables from the
               pos=h sweep; pitching rows come from the pitching table of the
               pos=p sweep (on some sites the two sweeps list different player
               pools). Pagination advances by rows-received and stops on a
               short page, an empty page, or a page with no new players.
Player log:    GET {site_base}/{sport_path}/{season}/players/{slug}
               Tab panes #gamelog-h / #gamelog-br / #gamelog-p all list the
               full team schedule; rows the player didn't appear in are all
               dashes and dates marked '#' are non-league games (both
               dropped). Cell text is parsed, not data-order attributes —
               thousands of those hold an unrendered template literal
               ("$tool.math.toDouble($value)").

Some sites (Sunbelt) sit behind AWS WAF: non-browser User-Agents get 403,
request bursts trigger a JS challenge served as HTTP 202 (backed off and
retried, never parsed), and offsets past the end of the players list return
HTTP 500 (treated as end of pagination once at least one page was read).
Inter-request spacing is configurable per league via `request_delay_s`.
"""
import datetime
import re
import time
from html.parser import HTMLParser

import requests

from pipeline import stats_math as sm

_TIMEOUT = 30
_DEFAULT_DELAY_S = 3.0      # cfg key `request_delay_s` overrides (WAF sites want ~10)
_PAGE_SIZE = 125            # rows per players-list page on every PrestoSports site seen
_CHALLENGE_TRIES = 4
_CHALLENGE_BACKOFF_S = 15.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/126.0.0.0 Safari/537.36"}


def _get_html(url):
    resp = None
    for attempt in range(1, _CHALLENGE_TRIES + 1):
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 202:      # AWS WAF JS challenge — back off, never parse
            if attempt < _CHALLENGE_TRIES:
                time.sleep(_CHALLENGE_BACKOFF_S * attempt)
            continue
        resp.raise_for_status()
        return resp.text
    raise requests.HTTPError(f"WAF challenge (HTTP 202) persisted for {url}",
                             response=resp)


def _throttle(cfg):
    time.sleep(cfg.get("request_delay_s", _DEFAULT_DELAY_S))


def _base_url(cfg):
    return f"{cfg['site_base'].rstrip('/')}/{cfg['sport_path'].strip('/')}/{cfg['season']}"


class _TableParser(HTMLParser):
    """Collect every <table> as lowercase headers + rows of (cell texts, slug).

    Tolerates the platform's malformed date cells ("Jun 4 </</td>"): a cell or
    row left open when the next one starts is flushed implicitly. Tables seen
    after an id="gamelog-*" element are tagged with that pane id.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._pane = None
        self._table = None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id", "").startswith("gamelog-"):
            self._pane = a["id"]
        if tag == "table":
            self._table = {"pane": self._pane, "headers": [], "rows": []}
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._end_row()
            self._row = {"cells": [], "slug": None, "th": False}
        elif tag in ("td", "th") and self._row is not None:
            self._end_cell()
            self._cell = []
            self._row["th"] |= tag == "th"
        elif tag == "a" and self._row is not None:
            href = a.get("href", "")
            if "/players/" in href and self._row["slug"] is None:
                self._row["slug"] = href.split("/players/")[-1].split("?")[0].strip("/")

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._end_cell()
        elif tag == "tr":
            self._end_row()
        elif tag == "table":
            self._end_row()
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def _end_cell(self):
        if self._cell is not None:
            self._row["cells"].append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None

    def _end_row(self):
        if self._row is None:
            return
        self._end_cell()
        if self._row["th"] and not self._table["headers"]:
            self._table["headers"] = [c.lower() for c in self._row["cells"]]
        elif not self._row["th"]:
            self._table["rows"].append(self._row)
        self._row = None


def _tables(html):
    p = _TableParser()
    p.feed(html)
    return p.tables


def _find_table(tables, must, must_not=(), pane=None):
    for t in tables:
        if pane is not None and t["pane"] != pane:
            continue
        heads = set(t["headers"])
        if all(h in heads for h in must) and not any(h in heads for h in must_not):
            return t
    return None


def _int(s):
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _cell(row, cols, key):
    idx = cols.get(key)
    return row["cells"][idx] if idx is not None and idx < len(row["cells"]) else ""


def _cols(table):
    return {h: i for i, h in enumerate(table["headers"])}


# canonical field -> site header, per table
_HIT_SIG, _BR_SIG, _PIT_SIG = ("ab", "rbi", "pa"), ("tb", "sb", "cs"), ("era", "ip", "bf")
_HIT_MAP = (("g", "gp"), ("ab", "ab"), ("h", "h"), ("d", "2b"), ("t", "3b"),
            ("hr", "hr"), ("rbi", "rbi"), ("bb", "bb"), ("k", "k"), ("hbp", "hbp"),
            ("sf", "sf"), ("sh", "sh"), ("pa", "pa"))
_BR_MAP = (("r", "r"), ("sb", "sb"), ("cs", "cs"))
_PIT_MAP = (("g", "app"), ("gs", "gs"), ("w", "w"), ("l", "l"), ("sv", "sv"),
            ("h", "h"), ("r", "r"), ("er", "er"), ("bb", "bb"), ("k", "k"),
            ("hb", "hbp"), ("hr", "hr"), ("bf", "bf"))


def _ident(row, cols):
    return {"stats_id": row["slug"], "name": _cell(row, cols, "name"),
            "team": _cell(row, cols, "team")}


def _extract_batting(tables):
    hit = _find_table(tables, _HIT_SIG, must_not=("era",))
    br = _find_table(tables, _BR_SIG, must_not=("po",))     # not the fielding table
    if hit is None:
        return {}
    hcols, out = _cols(hit), {}
    for row in hit["rows"]:
        if not row["slug"]:
            continue
        rec = _ident(row, hcols)
        rec.update({k: _int(_cell(row, hcols, h)) for k, h in _HIT_MAP})
        rec.update({k: 0 for k, _ in _BR_MAP})
        out[row["slug"]] = rec
    if br is not None:
        bcols = _cols(br)
        for row in br["rows"]:
            rec = out.get(row["slug"])
            if rec is not None:
                rec.update({k: _int(_cell(row, bcols, h)) for k, h in _BR_MAP})
    return out


def _extract_pitching(tables):
    pit = _find_table(tables, _PIT_SIG)
    if pit is None:
        return {}
    pcols, out = _cols(pit), {}
    for row in pit["rows"]:
        if not row["slug"]:
            continue
        rec = _ident(row, pcols)
        rec.update({k: _int(_cell(row, pcols, h)) for k, h in _PIT_MAP})
        rec["ip_outs"] = sm.ip_str_to_outs(_cell(row, pcols, "ip").replace("-", "") or 0)
        rec["hld"] = 0                       # not tracked on this platform
        out[row["slug"]] = rec
    return out


def _sweep(cfg, pos, sort, extract):
    out, start = {}, 0
    while True:
        url = f"{_base_url(cfg)}/players?pos={pos}&sort={sort}&start={start}"
        try:
            html = _get_html(url)
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", 0) or 0
            if start > 0 and code >= 500:
                break        # WAF sites answer 500 past the last row — end of list
            raise
        _throttle(cfg)
        page = extract(_tables(html))
        new = {sid: r for sid, r in page.items() if sid not in out}
        if not new:
            break            # empty page, or a clamped repeat of rows already seen
        out.update(new)
        if len(page) < _PAGE_SIZE:
            break            # short page = last page; don't probe past the end
        start += len(page)
    return list(out.values())


def fetch_league_stats(league_cfg):
    batting = _sweep(league_cfg, "h", "avg", _extract_batting)
    pitching = _sweep(league_cfg, "p", "era", _extract_pitching)
    return {
        "batting": [r for r in batting if r["g"] > 0],      # any appearance
        "pitching": [r for r in pitching if r["g"] > 0],
    }


_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _iso_date(short, year):
    parts = str(short).replace("#", " ").split()
    return f"{year}-{_MONTHS[parts[0][:3]]:02d}-{int(parts[1]):02d}"


def _season_year(cfg):
    return int(cfg.get("season") or datetime.date.today().year)


def _opponent(cell_text):
    return cell_text if cell_text.startswith("at ") else f"vs {cell_text}"


def _hit_games(tables, year):
    hit = _find_table(tables, ("date",), pane="gamelog-h")
    br = _find_table(tables, ("date",), pane="gamelog-br")
    if hit is None:
        return
    hcols = _cols(hit)
    bcols = _cols(br) if br is not None else {}
    brows = br["rows"] if br is not None else []
    for i, row in enumerate(hit["rows"]):
        date = _cell(row, hcols, "date")
        if "#" in date:                      # non-league game, absent from season totals
            continue
        b = brows[i] if i < len(brows) else None
        if b is not None and _cell(b, bcols, "date") != date:
            b = None                         # panes out of step — don't mis-merge
        r, sb, cs = (_int(_cell(b, bcols, h)) if b is not None else 0
                     for h in ("r", "sb", "cs"))
        if _int(_cell(row, hcols, "pa")) + r + sb + cs == 0:
            continue                         # scheduled/unplayed, or appeared without batting
        yield {"date": _iso_date(date, year), "opponent": _opponent(_cell(row, hcols, "opponent")),
               "ab": _int(_cell(row, hcols, "ab")), "r": r,
               "h": _int(_cell(row, hcols, "h")), "d": _int(_cell(row, hcols, "2b")),
               "t": _int(_cell(row, hcols, "3b")), "hr": _int(_cell(row, hcols, "hr")),
               "rbi": _int(_cell(row, hcols, "rbi")), "bb": _int(_cell(row, hcols, "bb")),
               "k": _int(_cell(row, hcols, "k")), "sb": sb}


def _pit_games(tables, year):
    pit = _find_table(tables, ("date",), pane="gamelog-p")
    if pit is None:
        return
    pcols = _cols(pit)
    for row in pit["rows"]:
        date = _cell(row, pcols, "date")
        if "#" in date:
            continue
        outs = sm.ip_str_to_outs(_cell(row, pcols, "ip").replace("-", "") or 0)
        w, l = _int(_cell(row, pcols, "w")), _int(_cell(row, pcols, "l"))
        h, r = _int(_cell(row, pcols, "h")), _int(_cell(row, pcols, "r"))
        k = _int(_cell(row, pcols, "k"))
        if outs + h + r + k + w + l == 0:
            continue                         # didn't pitch that game
        yield {"date": _iso_date(date, year), "opponent": _opponent(_cell(row, pcols, "opponent")),
               "ip_outs": outs, "h": h, "r": r, "er": _int(_cell(row, pcols, "er")),
               "bb": _int(_cell(row, pcols, "bb")),   # not shown per-game -> 0
               "k": k, "hr": _int(_cell(row, pcols, "hr")),
               "dec": "W" if w else "L" if l else ""}


def fetch_game_logs(league_cfg, stats_ids):
    year, logs = _season_year(league_cfg), {}
    for sid in stats_ids:
        try:
            html = _get_html(f"{_base_url(league_cfg)}/players/{sid}")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logs[sid] = []               # unknown/placeholder id — skip, don't fail the league
                _throttle(league_cfg)
                continue
            raise
        tables = _tables(html)
        entries = list(_hit_games(tables, year)) + list(_pit_games(tables, year))
        entries.sort(key=lambda e: e["date"], reverse=True)
        logs[sid] = entries
        _throttle(league_cfg)
    return logs

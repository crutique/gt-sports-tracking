"""StatBroadcast archive client -- enumeration and retrieval of StatCrew XML.

StatBroadcast archives completed games and publishes the **raw StatCrew XML**,
which is the scorer's own file rather than anyone's rendering of it. See
:mod:`pipeline.statcrew` for why that matters (HBP/SF/SH and batter K as fields,
explicit base-out state, handedness).

**Enumeration.** ``archive.statbroadcast.com`` is a public S3 bucket with
listing enabled, so the archive does not have to be guessed at. Objects are
``{sbid}.xml`` / ``.html`` / ``.pdf``, returned 1000 per page with a ``marker``
cursor. This matters because the site itself exposes no date or per-school
archive index, and ``sbid`` is **not** ordered by game date -- 651400 is April,
651570 is February -- so probing the id space would be both unreliable and rude.
Listing is ~2000 requests for the whole bucket.

``LastModified`` approximates when a game was archived, which is close enough to
the game date to pre-filter to the baseball window before fetching anything.

**Distinguishing baseball from softball.** Both are scored by the same software
and share the ``bsgame`` root element, so the sport is not stated. Scheduled
innings (``<venue schedinn>``) is the discriminator: 9 for baseball, 7 for
softball.

**Politeness.** ``statbroadcast.com/robots.txt`` disallows only ``/admin/``, and
the archive host serves no robots.txt at all, so nothing here is disallowed. We
still throttle and cache permanently -- an archived final game never changes, so
a backfill is paid for exactly once.
"""
import hashlib
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BUCKET = "http://archive.statbroadcast.com/"
LANDING = "https://www.statbroadcast.com/events/archived.php?id={sbid}"
_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
_UA = "GT-Summer-Tracker/1.0 (unofficial fan project)"
_TIMEOUT = 30
_THROTTLE_S = 0.4

CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "statbroadcast"
_last_call = [0.0]

#: Scheduled innings that identify baseball. Softball is scored by the same
#: software into the same ``bsgame`` shape but plays 7.
BASEBALL_INNINGS = 9


def _throttle():
    delta = time.monotonic() - _last_call[0]
    if delta < _THROTTLE_S:
        time.sleep(_THROTTLE_S - delta)
    _last_call[0] = time.monotonic()


def _get(url, timeout=_TIMEOUT):
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def list_objects(marker="", max_pages=None):
    """Yield ``(key, last_modified, size)`` for every object in the archive.

    ``marker`` resumes from a key, so a long enumeration can be checkpointed and
    restarted without repeating work.
    """
    pages = 0
    while max_pages is None or pages < max_pages:
        url = BUCKET + "?marker=" + urllib.parse.quote(marker)
        root = ET.fromstring(_get(url))
        contents = root.findall("s3:Contents", _NS)
        if not contents:
            return
        for c in contents:
            key = c.find("s3:Key", _NS).text or ""
            lm = (c.find("s3:LastModified", _NS).text or "")[:10]
            size = int((c.find("s3:Size", _NS).text or 0))
            marker = key
            yield key, lm, size
        pages += 1
        truncated = (root.find("s3:IsTruncated", _NS) is not None
                     and root.find("s3:IsTruncated", _NS).text == "true")
        if not truncated:
            return


def sbid_of(key):
    """``'651570.xml'`` -> ``'651570'``; ``None`` for anything not a plain id."""
    stem = key.split("/")[-1].split(".")[0]
    return stem if stem.isdigit() else None


def xml_url(sbid):
    return f"{BUCKET}{sbid}.xml"


def _cache_path(sbid):
    # shard so one directory never holds hundreds of thousands of entries
    s = str(sbid)
    return CACHE_DIR / s[-2:] / f"{s}.xml"


def fetch_xml(sbid, cache=True):
    """Raw StatCrew XML for ``sbid``. Cached forever -- final games are immutable.

    Returns ``None`` when the object does not exist (plenty of ids are absent or
    were never archived); callers record that as a gap rather than an error.
    """
    path = _cache_path(sbid)
    if cache and path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    try:
        body = _get(xml_url(sbid))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None
        raise
    text = body.decode("utf-8", errors="ignore")
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


#: Bytes to request when classifying. Must reach ``<venue schedinn>``, which sits
#: at offset 265-588 across 3000 sampled real files (present in 2998 of them).
_PEEK_BYTES = 1500


def peek_header(sbid):
    """Classify ``sbid`` from its first ~1.5 KB: ``(root_tag, sched_innings)``.

    The archive holds every sport StatBroadcast scores -- ``fbgame`` (football),
    ``bbgame`` (basketball), ``hkgame`` (hockey), ``bsgame`` (baseball/softball)
    -- and baseball is a minority of it. Fetching whole documents only to discard
    them wastes their bandwidth and our time: in one season's crawl **36% of all
    objects processed were softball**, each a ~50 KB download thrown away.

    Reading far enough to catch ``schedinn`` as well as the root tag rejects
    softball for ~1.5 KB instead of ~50 KB, so the only files fetched in full are
    ones we actually keep.

    ``sched_innings`` is 0 when the attribute is absent (rare -- 2 of 3000);
    callers fall back to downloading and counting innings for those.

    Returns ``(None, 0)`` if the object is absent or unreadable.
    """
    _throttle()
    req = urllib.request.Request(
        xml_url(sbid),
        headers={"User-Agent": _UA, "Range": f"bytes=0-{_PEEK_BYTES - 1}"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            head = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None, 0
        raise
    except Exception:
        return None, 0
    m = re.search(r"<([A-Za-z][A-Za-z0-9_]*)", head)
    root = m.group(1) if m else None
    innings = re.search(r'schedinn="(\d+)"', head)
    return root, int(innings.group(1)) if innings else 0


def peek_root(sbid):
    """Root element name only. Retained for callers that do not need innings."""
    return peek_header(sbid)[0]


def sha256(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def is_baseball(parsed):
    """True when a parsed game looks like baseball rather than softball.

    ``pipeline.statcrew.parse_game`` surfaces ``sched_innings`` from
    ``<venue schedinn>``. When it is absent -- some older files omit it -- fall
    back to whether the game actually reached a ninth inning.
    """
    sched = parsed.get("sched_innings")
    if sched:
        return sched >= BASEBALL_INNINGS
    return max((p["inning"] for p in parsed.get("plays") or []), default=0) >= 8

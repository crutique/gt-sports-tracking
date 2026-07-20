"""News scanner: fetch draft-signing snippets, extract via LLM, decide on publish tier.

Three layers, per docs/superpowers/specs/2026-07-20-draft-watch-design.md ("News
scanner"):

- fetch_snippets(player_name, session_get) -- pure I/O, `session_get` injected so
  tests run offline against fixtures. Pulls from Google News RSS, the MLB.com
  signing tracker, and GTSwarm's draft thread (last two pages), each isolated so
  one dead source never blanks the others.
- _extract(snippets, player_name) -- the sole Anthropic seam. Lazy-imports
  `anthropic` inside the function so importing this module (and running the
  offline test suite) never requires the package to be configured with a key.
  Malformed/unparseable model output always degrades to {"event": "none"}
  rather than raising -- a scan failure must never crash the watcher.
- decide(extraction, entry, today) -- PURE policy. No I/O, no LLM, fully
  unit-tested. See its docstring for the `_official_known` contract.
"""
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

WHITELIST = {"mlb.com", "milb.com", "mlbtraderumors.com", "si.com", "espn.com",
             "theathletic.com", "ajc.com", "nytimes.com", "cbssports.com"}

# Count of warnings emitted this run -- draft_watch resets it at start and
# surfaces the total in its summary line, so a broken scan can never
# masquerade as a quiet news day again (the Lackey/Burress lesson, 7/20).
WARNING_COUNT = 0


def _warn(msg):
    global WARNING_COUNT
    WARNING_COUNT += 1
    print(f"[news_scan] warning: {msg}")


def reset_warnings():
    global WARNING_COUNT
    WARNING_COUNT = 0

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/126.0.0.0 Safari/537.36"}
_SNIPPET_RADIUS = 300
_MLB_TRACKER_URL = "https://www.mlb.com/news/2026-draft-signing-and-bonus-tracker"
_GTSWARM_THREAD = "https://gtswarm.com/threads/2026-mlb-draft.31400/"
_MODEL = "claude-haiku-4-5-20251001"
_CLAUDE_CLI = "claude"

_PROMPT_TEMPLATE = (
    'You classify draft-signing news for MLB draftee {player_name}. From the snippets below,\n'
    'return ONE JSON object only: {{"event": "signed"|"expected"|"rumor"|"none",\n'
    '"amount": <int dollars or null>, "source_url": "<url of the snippet you relied on>",\n'
    '"quote": "<the exact sentence>"}}. "signed" ONLY for definitive completed-deal language\n'
    'about {player_name} himself (signed / agrees to terms / deal done) — hedged language\n'
    '(expects, likely, close to) is "expected"; secondhand chatter is "rumor"; anything else\n'
    'or a different person is "none". amount only if a specific dollar figure is stated.'
)


# ---------------------------------------------------------------------------
# fetch_snippets
# ---------------------------------------------------------------------------

class _TextStripper(HTMLParser):
    """Collapse an HTML blob down to plain whitespace-normalized text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def text(self):
        return " ".join(" ".join(self._parts).split())


def _strip_html(html):
    parser = _TextStripper()
    parser.feed(html)
    return parser.text()


class _GtswarmPostParser(HTMLParser):
    """Collect each forum post's stripped body text keyed by its post id.

    GTSwarm (XenForo) wraps each post in `<article class="message message--post
    ..." data-content="post-NNNN">` and the reply body in a `<div
    class="bbWrapper">`. bbWrapper bodies can contain nested `<div>`s (quoted
    blockquotes), so a naive non-greedy regex would close on the *first*
    nested `</div>` and truncate the reply -- this tracks div depth instead.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts = []
        self._post_id = None
        self._in_bbwrapper = False
        self._depth = 0
        self._buf = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "article" and "message--post" in (a.get("class") or ""):
            self._post_id = a.get("data-content")
        elif tag == "div" and a.get("class") == "bbWrapper" and not self._in_bbwrapper:
            self._in_bbwrapper = True
            self._depth = 1
            self._buf = []
        elif self._in_bbwrapper and tag == "div":
            self._depth += 1
        elif self._in_bbwrapper and tag == "br":
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if self._in_bbwrapper and tag == "div":
            self._depth -= 1
            if self._depth == 0:
                if self._post_id:
                    self.posts.append((self._post_id, "".join(self._buf)))
                self._in_bbwrapper = False
                self._buf = None

    def handle_data(self, data):
        if self._in_bbwrapper:
            self._buf.append(data)


def _decode(raw):
    return raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw


def _last_name(player_name):
    return player_name.strip().split()[-1]


def _window(text, last_name, radius=_SNIPPET_RADIUS):
    """±radius chars of `text` around the first case-insensitive hit of
    `last_name`, or None if it isn't present."""
    idx = text.lower().find(last_name.lower())
    if idx == -1:
        return None
    start = max(0, idx - radius)
    end = idx + len(last_name) + radius
    return text[start:end].strip()


def _rss_url(player_name):
    return f'https://news.google.com/rss/search?q=%22{player_name.replace(" ", "+")}%22+baseball'


def _fetch_rss_snippets(player_name, session_get):
    """Google News RSS item title+description, filtered to the player's last
    name. `url` is the outlet's published domain from the feed's <source>
    element (e.g. "https://www.si.com") rather than the <link>, which is only
    a news.google.com redirect wrapper -- the whitelist check in decide()
    needs the real publisher domain. Known trade-off: Google News RSS doesn't
    expose the per-article outlet URL, only the outlet's homepage, so two
    snippets from the same outlet dedupe together in fetch_snippets()."""
    last = _last_name(player_name)
    raw = session_get(_rss_url(player_name))
    root = ET.fromstring(raw)
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        desc = _strip_html(item.findtext("description") or "")
        combined = f"{title} {desc}".strip()
        if last.lower() not in combined.lower():
            continue
        source_el = item.find("source")
        url = ((source_el.get("url") if source_el is not None else None)
               or item.findtext("link") or "")
        if url:
            out.append({"text": title, "url": url})
    return out


def _fetch_mlb_tracker_snippets(player_name, session_get):
    last = _last_name(player_name)
    text = _strip_html(_decode(session_get(_MLB_TRACKER_URL)))
    snippet = _window(text, last)
    return [{"text": snippet, "url": _MLB_TRACKER_URL}] if snippet else []


def _last_gtswarm_page(html):
    nums = [int(n) for n in re.findall(r'draft\.31400/page-(\d+)', html)]
    return max(nums) if nums else 1


def _fetch_gtswarm_snippets(player_name, session_get):
    last = _last_name(player_name)
    page1_html = _decode(session_get(_GTSWARM_THREAD))
    last_page = _last_gtswarm_page(page1_html)
    target_pages = sorted({max(1, last_page - 1), last_page})
    out = []
    for n in target_pages:
        html = page1_html if n == 1 else _decode(
            session_get(f"{_GTSWARM_THREAD}page-{n}"))
        parser = _GtswarmPostParser()
        parser.feed(html)
        for post_id, text in parser.posts:
            snippet = _window(text, last)
            if snippet:
                out.append({"text": snippet,
                            "url": f"{_GTSWARM_THREAD}{post_id}"})
    return out


_SOURCES = (
    ("google-news-rss", _fetch_rss_snippets),
    ("mlb-tracker", _fetch_mlb_tracker_snippets),
    ("gtswarm", _fetch_gtswarm_snippets),
)


def default_session_get(url):
    """The production `session_get` for pipeline/draft_watch.py.

    fetch_snippets() takes `session_get` injected so tests stay offline; this
    is the real one — requests.get with the browser _HEADERS (GTSwarm and
    Google News both 403/302 plain-library UAs), a 30s timeout, and
    raise_for_status() so a dead source trips fetch_snippets' per-source
    isolation instead of feeding a parser an error page. Returns resp.content
    (bytes; every fetch_snippets source path decodes via _decode()).
    """
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content


def fetch_snippets(player_name, session_get):
    """Fetch news snippets for player_name, deduped by url.

    `session_get(url) -> str|bytes` is injected (fixtures in tests, a real
    requests.Session.get(...).content in production) so this stays testable
    offline. Each of the three sources is isolated in its own try/except: a
    dead source is logged and simply contributes nothing rather than blanking
    the whole call (per-source failure isolation, per the design spec).
    """
    snippets = []
    seen_urls = set()
    for label, fetcher in _SOURCES:
        try:
            for snip in fetcher(player_name, session_get):
                if snip["url"] not in seen_urls:
                    seen_urls.add(snip["url"])
                    snippets.append(snip)
        except Exception as exc:  # noqa: BLE001 -- isolate one dead source
            _warn(f"{label} fetch failed for {player_name!r}: {exc}")
    return snippets


# ---------------------------------------------------------------------------
# _extract -- the Anthropic seam
# ---------------------------------------------------------------------------

def _client():
    """The Anthropic client construction seam -- monkeypatched in tests so the
    suite never needs an API key or the network."""
    import anthropic
    return anthropic.Anthropic()


def _build_prompt(snippets, player_name):
    body = _PROMPT_TEMPLATE.format(player_name=player_name)
    blocks = "\n\n".join(
        f"[{i}] (source: {s['url']})\n{s['text']}"
        for i, s in enumerate(snippets, start=1)
    )
    return f"{body}\n\n{blocks}"


def _extract_cli(prompt):
    """Run `prompt` through the Claude Code CLI headlessly -- the
    subscription-token backend, for owners who authenticate with a Claude
    subscription (via `claude setup-token`) rather than an ANTHROPIC_API_KEY.

    `subprocess.run` is called with no `env=` override, so the subprocess
    inherits this process's environment -- that's how the CLI sees
    CLAUDE_CODE_OAUTH_TOKEN. Returns the CLI's stdout text on a clean (exit 0)
    run. Any subprocess-level failure (nonzero exit, timeout, missing `claude`
    binary) raises -- `_extract`'s single try/except is what degrades all of
    that, plus JSON-parsing and the name-guard failures below, to
    {"event": "none"}; this keeps the two backends' failure handling shared
    rather than duplicated.
    """
    result = subprocess.run(
        [_CLAUDE_CLI, "-p", prompt, "--model", _MODEL, "--output-format", "text"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {result.returncode}: "
            f"stderr={result.stderr.strip()[:200]!r} "
            f"stdout={result.stdout.strip()[:200]!r}")
    return result.stdout


def _parse_extraction(text, player_name):
    """Parse `text` as the single JSON object both backends produce, and apply
    the post-validation name guard. Shared by both the SDK and CLI backends so
    the guard behaves identically regardless of which one ran.

    Post-validation guard (spec: "exact player-name match required in the
    quote"): a non-none event whose quote does not contain the player's last
    name (case-insensitive) is downgraded to {"event": "none"} here, so a
    model answer that latched onto a teammate in the same snippet never
    reaches decide().
    """
    # The CLI backend (and occasionally the SDK) wraps the JSON in a markdown
    # fence AND may append explanatory prose after it (observed live 7/20).
    # Parse candidates in order: first fenced block anywhere, the whole text,
    # then the outermost {...} span amid surrounding prose.
    candidates = []
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text.strip())
    braced = re.search(r"\{.*\}", text, re.DOTALL)
    if braced:
        candidates.append(braced.group(0))
    data = None
    for cand in candidates:
        try:
            data = json.loads(cand)
            break
        except ValueError:
            continue
    if data is None:
        return {"event": "none"}
    if not isinstance(data, dict) or "event" not in data:
        return {"event": "none"}
    if data["event"] != "none":
        quote = str(data.get("quote") or "")
        if _last_name(player_name).lower() not in quote.lower():
            return {"event": "none"}
    return data


def _extract(snippets, player_name):
    """Classify `snippets` for player_name via Claude.

    Backend selection (checked in this order, every call):
      1. ANTHROPIC_API_KEY set (non-empty) -> the Anthropic SDK, via the lazy
         `_client()` seam (unchanged). This wins whenever both env vars are
         present -- a deterministic, documented precedence, so a runner
         configured with both always takes the SDK path.
      2. Otherwise, CLAUDE_CODE_OAUTH_TOKEN set (non-empty) -> `_extract_cli()`,
         which shells out to the Claude Code CLI headlessly, authenticated by
         that long-lived OAuth token (`claude setup-token`) -- for owners
         using a Claude subscription instead of a pay-per-token API key.
      3. Neither set -> {"event": "none"}; no backend is available.
    Presence is checked via `os.environ.get(...)` truthiness, not `in` --
    an empty-string env var (e.g. an unset GitHub Actions secret) is treated
    as absent, not present.

    Any failure -- network error, missing/invalid API key, a nonzero CLI
    exit, a CLI timeout, a missing `claude` binary, non-JSON or schema-less
    model output -- degrades to {"event": "none"} rather than raising, so a
    bad model response or backend failure never crashes the watcher run. The
    post-validation name guard (see `_parse_extraction`) applies identically
    to both backends.
    """
    prompt = _build_prompt(snippets, player_name)
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            client = _client()
            resp = client.messages.create(
                model=_MODEL, max_tokens=500, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
        elif os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            text = _extract_cli(prompt)
        else:
            return {"event": "none"}
        return _parse_extraction(text, player_name)
    except Exception as e:  # noqa: BLE001 -- malformed output must never crash the run
        _warn(f"extract failed for {player_name!r}: {type(e).__name__}: {str(e)[:200]}")
        return {"event": "none"}


# ---------------------------------------------------------------------------
# decide -- PURE publish policy
# ---------------------------------------------------------------------------

def _domain(url):
    return (urlparse(url).netloc or "").lower()


def _whitelisted(domain):
    """True if `domain` belongs to a WHITELIST outlet.

    Real feeds publish www-prefixed and sectioned hosts (the committed gnews
    fixture's SI source is literally https://www.si.com), so a bare set-
    membership test would misfile every such report as unverified. Normalize
    a leading "www." and treat each whitelist entry as a suffix: the entry
    itself or any subdomain of it (`endswith("." + d)` -- the dot keeps
    lookalikes like notsi.com out). The suffix rule on the mlb.com entry
    subsumes decide()'s original explicit `.mlb.com` special case.
    """
    if domain.startswith("www."):
        domain = domain[4:]
    return any(domain == d or domain.endswith("." + d) for d in WHITELIST)


def _official_known(entry):
    """True if `entry` already carries a known official signing bonus.

    Contract note: `entry` here is a pipeline/draft.yaml curated block (name,
    person_id, gt_role, reported, unverified, ...); draft.yaml itself has no
    "official bonus" field of its own -- the official figure comes from the
    live MLB picks API (pipeline/draft_status.py's fetch_picks(), via
    officialBonus). The plan's pseudocode calls _official_known(entry)
    without specifying how that picks-feed result reaches `entry`, so this
    module defines the contract explicitly: the caller (pipeline/draft_watch.py)
    is responsible for merging the picks-feed lookup into entry under the key
    "official_bonus" (e.g. `{**yaml_entry, "official_bonus": picks.get(pid,
    {}).get("officialBonus")}`) before calling decide(). This function just
    checks that merged key.
    """
    return entry.get("official_bonus") is not None


def decide(extraction, entry, today):
    """PURE publish policy. No I/O.

    Returns (tier, payload) where tier is "reported" | "unverified" | "flag" | None.
    """
    if extraction.get("event") == "signed" and isinstance(extraction.get("amount"), int):
        if entry.get("reported") or _official_known(entry):   # never downgrade/overwrite
            return None, None
        if _whitelisted(_domain(extraction["source_url"])):
            return "reported", {"bonus": extraction["amount"], "source": extraction["source_url"]}
        if (entry.get("unverified") or {}).get("source") == extraction["source_url"]:
            return None, None                                  # idempotent
        return "unverified", {"bonus": extraction["amount"],
                              "source": extraction["source_url"], "detected": today}
    if extraction.get("event") in ("signed", "expected", "rumor"):
        return "flag", {"event": extraction["event"], "source_url": extraction.get("source_url"),
                        "quote": extraction.get("quote", ""), "seen": today}
    return None, None

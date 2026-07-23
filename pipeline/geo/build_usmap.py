#!/usr/bin/env python3
"""Regenerate site/src/data/usmap.json for the "By league" map.

Projects US state outlines AND the GT summer-team cities through one shared
Albers conic projection, so the map's land and its plotted dots are guaranteed
to align. The seven Cape Cod towns cluster too tightly to read at national
scale, so they also get a local re-projection for the zoom inset.

Inputs (both in this directory):
  - us-states.geo.json : public-domain US state boundaries (Census-derived)
  - league_geo.json    : real home cities (lat/lon) of the 16 GT summer teams

Run from anywhere:  python3 pipeline/geo/build_usmap.py
Re-run whenever a team's league assignment or the team set changes.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "site", "src", "data", "usmap.json")

geo = json.load(open(os.path.join(HERE, "us-states.geo.json")))
teams = json.load(open(os.path.join(HERE, "league_geo.json")))

# --- Albers equal-area conic (d3.geoAlbers continental defaults) ---
P1, P2, LON0, LAT0 = math.radians(29.5), math.radians(45.5), math.radians(-96), math.radians(37.5)
n = (math.sin(P1) + math.sin(P2)) / 2
C = math.cos(P1) ** 2 + 2 * n * math.sin(P1)
rho0 = math.sqrt(C - 2 * n * math.sin(LAT0)) / n


def project(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    theta = n * (lam - LON0)
    rho = math.sqrt(C - 2 * n * math.sin(phi)) / n
    return (rho * math.sin(theta), rho0 - rho * math.cos(theta))


EXCLUDE = {"Alaska", "Hawaii", "Puerto Rico"}  # keep the continental frame the teams live in

rings = []
for f in geo["features"]:
    name = f["properties"]["name"]
    if name in EXCLUDE:
        continue
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    prings = [[project(lon, lat) for lon, lat in ring] for poly in polys for ring in poly]
    rings.append((name, prings))

xs = [p[0] for _, pr in rings for r in pr for p in r]
ys = [p[1] for _, pr in rings for r in pr for p in r]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

TARGET_W, PAD = 960.0, 16.0
scale = (TARGET_W - 2 * PAD) / (maxx - minx)
H = (maxy - miny) * scale + 2 * PAD


def fit(x, y):
    return ((x - minx) * scale + PAD, (maxy - y) * scale + PAD)


def simplify(pts, eps=1.4):
    """distance-threshold decimation in screen space — drops coastline jitter"""
    out = [pts[0]]
    for p in pts[1:]:
        lx, ly = out[-1]
        if (p[0] - lx) ** 2 + (p[1] - ly) ** 2 >= eps * eps:
            out.append(p)
    return out if len(out) >= 3 else pts


def path_for(prings):
    d = []
    for ring in prings:
        fpts = simplify([fit(x, y) for x, y in ring])
        if len(fpts) >= 3:
            d.append("M" + " ".join(f"{x:.1f},{y:.1f}" for x, y in fpts) + "Z")
    return "".join(d)


states = [{"name": nm, "d": path_for(pr)} for nm, pr in rings]


def fit_lonlat(lon, lat):
    return fit(*project(lon, lat))


team_pts = {}
for nm, t in teams["teams"].items():
    x, y = fit_lonlat(t["lon"], t["lat"])
    team_pts[nm] = {"x": round(x, 1), "y": round(y, 1), "league": t["league"], "city": t["city"]}

home = teams["gt_home"]
hx, hy = fit_lonlat(home["lon"], home["lat"])
home_pt = {"x": round(hx, 1), "y": round(hy, 1), "city": home["city"]}

# --- Cape Cod inset: the real coastline as background + towns on top ---
# A high-res Massachusetts coastline is clipped to a lon/lat box around the Cape
# (canal/Wareham west → Provincetown tip), projected through ONE local fit so
# the whole hooked peninsula shows and each town sits at its true spot on it.
cape = {nm: t for nm, t in teams["teams"].items() if t["league"] == "cape_cod"}
ma = json.load(open(os.path.join(HERE, "ma-coastline.geojson")))
mg = ma["geometry"] if ma.get("type") == "Feature" else ma["features"][0]["geometry"]
ma_polys = mg["coordinates"] if mg["type"] == "MultiPolygon" else [mg["coordinates"]]

CW, CS, CE, CN = -70.86, 41.51, -69.9, 42.12  # Cape clip window (lon/lat)


def _clip_edge(ring, inside, isect):
    out, nring = [], len(ring)
    for i in range(nring):
        a, b = ring[i], ring[(i + 1) % nring]
        ina, inb = inside(a), inside(b)
        if ina:
            out.append(a)
            if not inb:
                out.append(isect(a, b))
        elif inb:
            out.append(isect(a, b))
    return out


def clip_rect(ring, w, s, e, nn):
    def ix(a, b, t):
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]

    ring = _clip_edge(ring, lambda p: p[0] >= w, lambda a, b: ix(a, b, (w - a[0]) / (b[0] - a[0])))
    if len(ring) < 3: return []
    ring = _clip_edge(ring, lambda p: p[0] <= e, lambda a, b: ix(a, b, (e - a[0]) / (b[0] - a[0])))
    if len(ring) < 3: return []
    ring = _clip_edge(ring, lambda p: p[1] >= s, lambda a, b: ix(a, b, (s - a[1]) / (b[1] - a[1])))
    if len(ring) < 3: return []
    ring = _clip_edge(ring, lambda p: p[1] <= nn, lambda a, b: ix(a, b, (nn - a[1]) / (b[1] - a[1])))
    return ring if len(ring) >= 3 else []


cape_rings = []
for _poly in ma_polys:
    for _ring in _poly:
        _cr = clip_rect(_ring, CW, CS, CE, CN)
        if _cr:
            cape_rings.append(_cr)

land_proj = [[project(lon, lat) for lon, lat in r] for r in cape_rings]
lxs = [p[0] for r in land_proj for p in r]
lys = [p[1] for r in land_proj for p in r]
lminx, lmaxx, lminy, lmaxy = min(lxs), max(lxs), min(lys), max(lys)
lw, lh = (lmaxx - lminx) or 1, (lmaxy - lminy) or 1

INSET_W, INSET_H = 320.0, 236.0
LX0, LY0, LX1, LY1 = 18.0, 50.0, INSET_W - 18.0, INSET_H - 16.0  # land area (title band above)
law, lah = LX1 - LX0, LY1 - LY0
ls = min(law / lw, lah / lh)
lox = LX0 + (law - lw * ls) / 2
loy = LY0 + (lah - lh * ls) / 2


def cape_fit(lon, lat):
    x, y = project(lon, lat)
    return (lox + (x - lminx) * ls, loy + (lmaxy - y) * ls)


def cape_land_path():
    d = []
    for r in cape_rings:
        fpts = simplify([cape_fit(lon, lat) for lon, lat in r], eps=0.8)
        if len(fpts) >= 3:
            d.append("M" + " ".join(f"{x:.1f},{y:.1f}" for x, y in fpts) + "Z")
    return "".join(d)


cape_land = cape_land_path()
cape_pts = {
    nm: {"x": round(cape_fit(t["lon"], t["lat"])[0], 1), "y": round(cape_fit(t["lon"], t["lat"])[1], 1)}
    for nm, t in cape.items()
}

out = {
    "viewBox": [round(TARGET_W, 1), round(H, 1)],
    "states": states,
    "teams": team_pts,
    "home": home_pt,
    "inset": {"w": INSET_W, "h": INSET_H, "land": cape_land, "teams": cape_pts},
}
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(f"wrote {OUT}: viewBox {out['viewBox']}, {len(states)} states, {len(team_pts)} teams, {len(cape_pts)} Cape towns")

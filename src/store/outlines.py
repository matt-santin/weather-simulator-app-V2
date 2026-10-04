"""Country outlines for the map page and the home icon, from Natural Earth.

    python -m src.store.outlines

Source: Natural Earth 1:50m admin 0 countries (public domain,
naturalearthdata.com), data/fixed/ne_50m_admin_0_countries.geojson.

Writes two static files under web/static/:

- geo/europe.json: the rings of every country that reaches into BOX,
  simplified (Douglas-Peucker, TOLERANCE degrees) and rounded to 0.01 deg.
  The map page draws them over the cells; the canvas clips what runs outside.
- icons/europe.svg: the outline of Europe for the home page, traced from the
  land mask of the map store (data/serve/map.zarr), coarsened to 0.5 deg:
  one coastline, no borders between countries. Build the map store first.
"""

from __future__ import annotations

import json
import math
import sys

from src.config import DATA, ROOT

SOURCE = DATA / "fixed" / "ne_50m_admin_0_countries.geojson"
WEB = ROOT / "web" / "static"
BOX = {"west": -25.0, "east": 45.0, "south": 34.0, "north": 72.0}
TOLERANCE = 0.03  # degrees
ICON_BOX = {"west": -11.0, "east": 33.0, "south": 35.5, "north": 71.0}
ICON_TOLERANCE = 0.4


def simplify(ring: list[list[float]], tolerance: float) -> list[list[float]]:
    """Douglas-Peucker on a ring, in degrees; the ends are kept."""
    if len(ring) < 4:
        return ring

    def distance(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return math.hypot(x - x1, y - y1)
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - x1 - t * dx, y - y1 - t * dy)

    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        i, j = stack.pop()
        far, at = 0.0, None
        for k in range(i + 1, j):
            d = distance(ring[k], ring[i], ring[j])
            if d > far:
                far, at = d, k
        if at is not None and far > tolerance:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, k in zip(ring, keep) if k]


def rings(box: dict, tolerance: float) -> list[list[list[float]]]:
    """Every outer and inner ring of the countries reaching into box."""
    out = []
    for feature in json.loads(SOURCE.read_text())["features"]:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            for ring in polygon:
                xs, ys = [p[0] for p in ring], [p[1] for p in ring]
                if max(xs) < box["west"] or min(xs) > box["east"] or max(ys) < box["south"] or min(ys) > box["north"]:
                    continue
                small = simplify(ring, tolerance)
                if len(small) >= 4:
                    out.append([[round(x, 2), round(y, 2)] for x, y in small])
    return out


def write_map() -> None:
    path = WEB / "geo" / "europe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"source": "Natural Earth 1:50m, domaine public", "box": BOX, "rings": rings(BOX, TOLERANCE)}
    path.write_text(json.dumps(data, separators=(",", ":")))
    print(f"{path} : {len(data['rings'])} contours, {path.stat().st_size / 1e3:.0f} ko")


def write_icon() -> None:
    """A 64 x 64 outline, in the same flattened projection as the map."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import zarr

    from src.store.maps import STORE

    root = zarr.open_group(STORE, mode="r")
    lat, lon, land = root["latitude"][:], root["longitude"][:], root["land"][:].astype(float)
    # 0.25 to 0.5 deg: two by two cells averaged.
    ny, nx = land.shape[0] // 2 * 2, land.shape[1] // 2 * 2
    coarse = land[:ny, :nx].reshape(ny // 2, 2, nx // 2, 2).mean(axis=(1, 3))
    clat = lat[:ny].reshape(-1, 2).mean(axis=1)
    clon = lon[:nx].reshape(-1, 2).mean(axis=1)
    # A sea border, so that every coastline closes.
    coarse = np.pad(coarse, 1)
    clat = np.concatenate([[clat[0] + 0.5], clat, [clat[-1] - 0.5]])
    clon = np.concatenate([[clon[0] - 0.5], clon, [clon[-1] + 0.5]])
    contour = plt.contour(clon, clat, coarse, levels=[0.5])
    lines = contour.get_paths()[0].to_polygons() if contour.get_paths() else []
    plt.close("all")

    b = ICON_BOX
    k = math.cos(math.radians(53))
    width, height = (b["east"] - b["west"]) * k, b["north"] - b["south"]
    scale = 60 / max(width, height)
    ox, oy = (64 - width * scale) / 2, (64 - height * scale) / 2

    def xy(lon, lat):
        return f"{ox + (lon - b['west']) * k * scale:.1f},{oy + (b['north'] - lat) * scale:.1f}"

    paths = []
    for line in lines:
        lons, lats = line[:, 0], line[:, 1]
        if lons.max() < b["west"] or lons.min() > b["east"] or lats.max() < b["south"] or lats.min() > b["north"]:
            continue
        # Small islands are noise at 64 px.
        if (lons.max() - lons.min()) * (lats.max() - lats.min()) < 4.0:
            continue
        ring = simplify(line.tolist(), ICON_TOLERANCE)
        paths.append("M" + " L".join(xy(x, y) for x, y in ring) + "Z")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">'
        '<defs><clipPath id="frame"><rect width="64" height="64"/></clipPath></defs>'
        f'<path clip-path="url(#frame)" d="{" ".join(paths)}" stroke="currentColor" stroke-width="2" '
        'stroke-linejoin="round"/></svg>'
    )
    path = WEB / "icons" / "europe.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg)
    print(f"{path} : {len(paths)} contours, {path.stat().st_size / 1e3:.1f} ko")


def main() -> int:
    write_map()
    write_icon()
    return 0


if __name__ == "__main__":
    sys.exit(main())

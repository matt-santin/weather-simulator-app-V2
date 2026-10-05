/**
 * The arithmetic of the map page: bands, projection, the grid of cells, and the
 * summary of a day. No DOM, no fetching: `node --test` checks it.
 *
 * **Each variable has its bands.** The maxima use the site's, served by
 * /api/config (the five degrees the cards and the chart use): nine colours for
 * eight edges, the last (40 °C and above) hatched by the page. The minima keep
 * five degrees but run colder, from -20 to 30 °C, with a clear turn at 0 °C
 * (frost) and at 20 °C (warm nights, Tn > 20 °C as in
 * figures/climat/france_indicateurs.py). Rain is cut at
 * 1 mm, the threshold of a rainy day (DRIAS, Météo-France), then 5, 10, 20 and
 * 50 mm; cloud cover in fifths.
 *
 * **The projection is Lambert azimuthal equal-area centred on Europe**, with its
 * inverse, which the tooltip needs.
 */

/** One colour per band of temperature, from below the first edge to above the last. */
export const COLORS = [
  "#123a72",
  "#5aa9de",
  "#8bc94a",
  "#f2ce1b",
  "#f0902a",
  "#e9634a",
  "#b01712",
  "#6b0a0a",
  "#16100c",
];

/** The minima: 12 colours for 11 edges, violet in the deep cold, blue to 0 °C. */
export const MINIMA_EDGES = [-20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30];
export const MINIMA_COLORS = [
  "#efdff6",
  "#c39bd3",
  "#8e5cad",
  "#4b3a8f",
  "#1f4f9c",
  "#4f95d0",
  "#9fd0e6",
  "#a6d36a",
  "#f2ce1b",
  "#f0902a",
  "#d9452f",
  "#8a0f0f",
];

/**
 * What each variable is drawn with. `edges: null` means the edges served by
 * /api/config for the temperatures. `first` and `second` are the two figures of
 * the panel: the highest or the lowest cell, the median, or the share of cells
 * in the first band (dry, clear). `timeline` is what each day's bar shows.
 */
export const VARIABLES = {
  tasmax: {
    unit: "°C",
    decimals: 1,
    colors: COLORS,
    edges: null,
    hatchTop: true,
    first: "max",
    second: "median",
    timeline: "median",
  },
  tasmin: {
    unit: "°C",
    decimals: 1,
    colors: MINIMA_COLORS,
    edges: MINIMA_EDGES,
    hatchTop: false,
    first: "min",
    second: "median",
    timeline: "median",
  },
  pr: {
    unit: "mm",
    decimals: 1,
    colors: ["#4a4136", "#bfe0f5", "#6aaed6", "#2b7bba", "#7b4fa8", "#e05fb0"],
    edges: [1, 5, 10, 20, 50],
    hatchTop: false,
    first: "max",
    second: "share",
    timeline: "mean",
  },
  clt: {
    unit: "%",
    decimals: 0,
    colors: ["#f2ce1b", "#d6c27a", "#a8a596", "#7f7f86", "#5d5f69"],
    edges: [20, 40, 60, 80],
    hatchTop: false,
    first: "median",
    second: "share",
    timeline: "median",
  },
};

/** Missing value in the integers /api/map serves (tenths of a degree). */
export const FILL = -32768;

/** The band of a temperature: 0 below the first edge, edges.length above the last. */
export function band(value, edges) {
  let index = 0;
  while (index < edges.length && value >= edges[index]) index += 1;
  return index;
}

/**
 * Lambert azimuthal equal-area, centred on Europe (52° N, 10° E), on the
 * sphere: the projection of the European statistical maps (ETRS89-LAEA). The
 * meridians close in towards the north and the parallels curve, so the map
 * reads as a piece of the globe; areas are kept, which suits a share of cells.
 */
const CENTRE = { lat: 52, lon: 10 };
const RAD = Math.PI / 180;
const SIN0 = Math.sin(CENTRE.lat * RAD);
const COS0 = Math.cos(CENTRE.lat * RAD);

/** Longitude and latitude in degrees to the plane, in Earth radii. */
export function laea(lon, lat) {
  const phi = lat * RAD;
  const dl = (lon - CENTRE.lon) * RAD;
  const k = Math.sqrt(2 / (1 + SIN0 * Math.sin(phi) + COS0 * Math.cos(phi) * Math.cos(dl)));
  return [
    k * Math.cos(phi) * Math.sin(dl),
    k * (COS0 * Math.sin(phi) - SIN0 * Math.cos(phi) * Math.cos(dl)),
  ];
}

/** The plane back to longitude and latitude in degrees. */
export function unlaea(x, y) {
  const rho = Math.hypot(x, y);
  if (rho === 0) return [CENTRE.lon, CENTRE.lat];
  const c = 2 * Math.asin(Math.min(1, rho / 2));
  const lat = Math.asin(Math.cos(c) * SIN0 + (y * Math.sin(c) * COS0) / rho);
  const lon =
    CENTRE.lon * RAD +
    Math.atan2(x * Math.sin(c), rho * COS0 * Math.cos(c) - y * SIN0 * Math.sin(c));
  return [lon / RAD, lat / RAD];
}

/**
 * The frame: the rectangle, on the projected plane, around the given points
 * (longitude, latitude), with a margin in degrees. The map page passes the
 * corners of its cells, so that the land fills the frame and the empty corners
 * the projection opens (Greenland, beyond the domain's eastern edge) are cut.
 */
export function frame(points, margin = 0) {
  let left = Infinity;
  let right = -Infinity;
  let top = -Infinity;
  let bottom = Infinity;
  const offsets = [
    [-margin, -margin],
    [margin, margin],
    [-margin, margin],
    [margin, -margin],
  ];
  for (const [lon, lat] of points) {
    for (const [dx, dy] of offsets) {
      const [x, y] = laea(lon + dx, lat + dy);
      left = Math.min(left, x);
      right = Math.max(right, x);
      top = Math.max(top, y);
      bottom = Math.min(bottom, y);
    }
  }
  return { left, right, top, bottom };
}

/** The frame around a box of longitudes and latitudes, edges walked a degree at a time. */
export function boxFrame(box) {
  const points = [];
  for (let lon = box.west; lon <= box.east; lon += 1) {
    points.push([lon, box.south], [lon, box.north]);
  }
  for (let lat = box.south; lat <= box.north; lat += 1) {
    points.push([box.west, lat], [box.east, lat]);
  }
  return frame(points);
}

/** Map coordinates to pixels and back, for a frame drawn `width` pixels wide. */
export function projection({ left, right, top, bottom }, width) {
  const scale = width / (right - left);
  return {
    width,
    height: (top - bottom) * scale,
    project: (lon, lat) => {
      const [x, y] = laea(lon, lat);
      return [(x - left) * scale, (top - y) * scale];
    },
    unproject: (px, py) => unlaea(left + px / scale, top - py / scale),
  };
}

/**
 * The cells as a small image: the rows and columns /api/map/cells serves,
 * shifted so that the first used row and column are 0. `index` finds the cell
 * under a row and column of that image, for the tooltip.
 */
export function grid(cells) {
  const top = Math.min(...cells.rows);
  const left = Math.min(...cells.cols);
  const rows = Math.max(...cells.rows) - top + 1;
  const cols = Math.max(...cells.cols) - left + 1;
  const index = new Map();
  const at = cells.rows.map((row, k) => {
    const pixel = (row - top) * cols + (cells.cols[k] - left);
    index.set(pixel, k);
    return pixel;
  });
  return {
    rows,
    cols,
    at,
    index,
    // The outer edges of the image, in degrees: cell centres plus half a step.
    north: cells.north - top * cells.step + cells.step / 2,
    west: cells.west + left * cells.step - cells.step / 2,
    step: cells.step,
    latitude: (k) => cells.north - cells.rows[k] * cells.step,
    longitude: (k) => cells.west + cells.cols[k] * cells.step,
  };
}

/** The values of one day, in degrees, out of the integers for all days. */
export function day(values, cells, index) {
  return values.subarray(index * cells, (index + 1) * cells);
}

/** Highest and lowest cells, median, mean and the count of cells in each band, for one day. */
export function summary(tenths, edges) {
  const counts = new Array(edges.length + 1).fill(0);
  const sorted = [];
  let hottest = null;
  let at = -1;
  let coldest = null;
  let coldAt = -1;
  let total = 0;
  for (let k = 0; k < tenths.length; k += 1) {
    if (tenths[k] === FILL) continue;
    const value = tenths[k] / 10;
    sorted.push(value);
    total += value;
    counts[band(value, edges)] += 1;
    if (hottest === null || value > hottest) {
      hottest = value;
      at = k;
    }
    if (coldest === null || value < coldest) {
      coldest = value;
      coldAt = k;
    }
  }
  sorted.sort((a, b) => a - b);
  const n = sorted.length;
  const median = n === 0 ? null : n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  return { hottest, at, coldest, coldAt, median, mean: n ? total / n : null, counts, cells: n };
}

/** How far the map zooms in, and the view it opens on. */
export const MAX_ZOOM = 12;
export const WHOLE = { scale: 1, x: 0, y: 0 };

/**
 * The zoom as a scale and an offset, the offset in fractions of the map's width
 * and height so that it survives a resize. A point at (px, py) on the map
 * drawn whole is shown at (px * scale + x * width, py * scale + y * height).
 * The offset is held so that the map always covers its frame: no empty band
 * opens at an edge.
 */
function clamped({ scale, x, y }) {
  const low = 1 - scale;
  return { scale, x: Math.min(0, Math.max(low, x)), y: Math.min(0, Math.max(low, y)) };
}

/** Zoom by `factor` keeping the point (cx, cy) of the frame where it is. */
export function zoomAt(zoom, factor, cx, cy, width, height) {
  const scale = Math.min(MAX_ZOOM, Math.max(1, zoom.scale * factor));
  const k = scale / zoom.scale;
  const x = (cx - (cx - zoom.x * width) * k) / width;
  const y = (cy - (cy - zoom.y * height) * k) / height;
  return clamped({ scale, x, y });
}

/** Move the zoomed map by (dx, dy) pixels. */
export function pan(zoom, dx, dy, width, height) {
  return clamped({ scale: zoom.scale, x: zoom.x + dx / width, y: zoom.y + dy / height });
}

/** The point of the map drawn whole that is under (x, y) of the frame. */
export function unzoom(zoom, x, y, width, height) {
  return [(x - zoom.x * width) / zoom.scale, (y - zoom.y * height) / zoom.scale];
}

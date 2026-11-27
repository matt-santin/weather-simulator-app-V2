/**
 * The arithmetic of the page /climats: the Köppen-Geiger classes of 1991-2020
 * and 2071-2100 over Europe. No DOM, no fetching: `node --test` checks it.
 *
 * The classes come as two small grey images (src/store/koppen.py): one pixel
 * per 0.1 deg cell, row 0 to the north, the number of the class in the legend
 * of Beck et al. 2023 (`codes` of koppen.json), 0 for none. The page draws
 * them once each, in the projection of the map page (mapview.js), into an
 * image the zoom only scales: `paint` fills its pixels.
 */

/** The colours of Beck et al. 2023 (legend.txt of their maps), so that ours read like theirs. */
export const COLORS = {
  Af: "#0000ff",
  Am: "#0078ff",
  Aw: "#46aafa",
  BWh: "#ff0000",
  BWk: "#ff9696",
  BSh: "#f5a500",
  BSk: "#ffdc64",
  Csa: "#ffff00",
  Csb: "#c8c800",
  Csc: "#969600",
  Cwa: "#96ff96",
  Cwb: "#64c864",
  Cwc: "#329632",
  Cfa: "#c8ff50",
  Cfb: "#64ff50",
  Cfc: "#32c800",
  Dsa: "#ff00ff",
  Dsb: "#c800c8",
  Dsc: "#963296",
  Dsd: "#966496",
  Dwa: "#aaafff",
  Dwb: "#5a78dc",
  Dwc: "#4b50b4",
  Dwd: "#320087",
  Dfa: "#00ffff",
  Dfb: "#37c8ff",
  Dfc: "#007d7d",
  Dfd: "#00465f",
  ET: "#b2b2b2",
  EF: "#666666",
};

/** The index of the cell holding a point in the grid of koppen.json, or -1 outside it. */
export function cellOf(meta, lon, lat) {
  const row = Math.round((meta.north - lat) / meta.step);
  const col = Math.round((lon - meta.west) / meta.step);
  if (row < 0 || col < 0 || row >= meta.rows || col >= meta.cols) return -1;
  return row * meta.cols + col;
}

/** The code of the class at a point ("Cfb"), or "" over the sea and outside. */
export function classAt(meta, classes, lon, lat) {
  const k = cellOf(meta, lon, lat);
  return k < 0 ? "" : meta.codes[classes[k]] ?? "";
}

/** The classes present in any of the grids, in the order of the legend. */
export function present(meta, ...grids) {
  const seen = new Set();
  for (const grid of grids) for (const value of grid) if (value) seen.add(value);
  return [...seen].sort((a, b) => a - b).map((value) => meta.codes[value]).filter(Boolean);
}

/** "#64ff50" to [100, 255, 80]. */
export function rgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/**
 * The pixels of the map drawn whole, `width` x `height`, as RGBA: each pixel
 * takes the class of the cell under its centre (`unproject` gives its longitude
 * and latitude), transparent over the sea.
 */
export function paint(meta, classes, width, height, unproject) {
  const colours = meta.codes.map((code) => (code && COLORS[code] ? rgb(COLORS[code]) : null));
  const pixels = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const [lon, lat] = unproject(x + 0.5, y + 0.5);
      const k = cellOf(meta, lon, lat);
      if (k < 0) continue;
      const colour = colours[classes[k]];
      if (!colour) continue;
      const p = (y * width + x) * 4;
      pixels[p] = colour[0];
      pixels[p + 1] = colour[1];
      pixels[p + 2] = colour[2];
      pixels[p + 3] = 255;
    }
  }
  return pixels;
}

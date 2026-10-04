/**
 * The matrix of years: one tile per year from 1970 to 2100, the dates of the
 * search in each, coloured by how far its mean temperature sits from the
 * reference period. The server measures and classes every year
 * (`/api/years`); this file only turns that into tiles and sentences.
 *
 * **The colour is the anomaly in standard deviations, clamped at three**, on
 * a scale blue, green, yellow (the normal), orange, red. The year is written in
 * white or in dark ink, whichever stands out more on the tile: white on the
 * blues, greens and reds, ink on the yellow and the oranges. At least 4,5:1
 * everywhere.
 */

import { el } from "./dom.js";
import { texts } from "./i18n.js";

/** Where the scale saturates, in standard deviations. */
export const CLAMP = 3;

/** The scale, from -CLAMP to +CLAMP, five stops evenly spaced. */
export const STOPS = [
  [33, 102, 172], // blue
  [24, 128, 56], // green
  [242, 197, 61], // yellow: the normal
  [240, 124, 30], // orange
  [198, 40, 40], // red
];

/** The tile colour of an anomaly in standard deviations, as [r, g, b]. */
export function rgb(sigmas) {
  const t = (Math.max(-1, Math.min(1, sigmas / CLAMP)) + 1) / 2; // 0 to 1
  const at = t * (STOPS.length - 1);
  const low = Math.min(Math.floor(at), STOPS.length - 2);
  const share = at - low;
  return STOPS[low].map((value, index) =>
    Math.round(value + (STOPS[low + 1][index] - value) * share),
  );
}

/** The same, as "rgb(r, g, b)". */
export function color(sigmas) {
  return `rgb(${rgb(sigmas).join(", ")})`;
}

/** The dark ink, where white would not hold on the tile. */
export const INK = [0, 0, 0];

/** WCAG contrast ratio between two colours. */
export function contrast(a, b) {
  const luminance = (c) => {
    const [r, g, bl] = c.map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

/** White or the dark ink, whichever stands out more on the tile. */
export function textColor(sigmas) {
  const tile = rgb(sigmas);
  return contrast(tile, [255, 255, 255]) >= contrast(tile, INK) ? "#fff" : `rgb(${INK.join(", ")})`;
}

const ONE_DECIMAL = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const SIGNED = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

/** "20,3" and "+1,4": the matrix reads tenths, where a card reads whole degrees. */
export const decimal = (value) => ONE_DECIMAL.format(value);
export const signed = (value) => SIGNED.format(value);

/**
 * The tiles, in order: ten to a row in the stylesheet, so each row is a
 * decade. A year with no values (2026) is a disabled tile; a simulated one
 * carries the class that marks it. `pick` is called with the year clicked.
 */
export function tiles(answer, pick) {
  return answer.years.map((year) => {
    if (year.temperature_mean === null || year.temperature_sigmas === null) {
      return el("button", {
        className: "year-tile none",
        text: String(year.year),
        attrs: { type: "button", disabled: "disabled", "aria-label": texts.years.unavailable(year.year) },
      });
    }
    const tile = el("button", {
      className: year.origin === "simulated" ? "year-tile simulated" : "year-tile",
      text: String(year.year),
      attrs: {
        type: "button",
        style: `background-color: ${color(year.temperature_sigmas)}; color: ${textColor(year.temperature_sigmas)}`,
        "aria-pressed": "false",
        "aria-label": texts.years.tileLabel(
          year.year,
          decimal(year.temperature_mean),
          texts.years.temperature[year.temperature_class],
        ),
      },
    });
    tile.addEventListener("click", () => pick(year, tile));
    return tile;
  });
}

/** The two sentences shown when a tile is clicked. */
export function detail(answer, year) {
  const reference = `${answer.reference_start.slice(0, 4)}-${answer.reference_end.slice(0, 4)}`;
  const lines = [
    texts.years.temperatureLine(
      decimal(year.temperature_mean),
      signed(year.temperature_anomaly),
      reference,
      texts.years.temperature[year.temperature_class],
    ),
  ];
  if (year.precipitation !== null && year.precipitation_ratio !== null) {
    lines.push(
      texts.years.rainLine(
        String(Math.round(year.precipitation)),
        String(Math.round(year.precipitation_ratio * 100)),
        texts.years.rain[year.precipitation_class],
      ),
    );
  }
  return lines;
}

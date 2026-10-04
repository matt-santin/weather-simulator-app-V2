/**
 * The matrix of years: the colour follows the anomaly and saturates, a year
 * without values cannot be clicked, a simulated one says so, and the detail
 * reads the server's classes.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { install } from "./dom-stub.js";

install();
const { CLAMP, INK, color, contrast, detail, rgb, signed, textColor, tiles } = await import("../../web/static/js/matrix.js");

const year = (value, extra = {}) => ({
  year: value,
  start: `${value}-06-21`,
  end: `${value}-09-20`,
  origin: value >= 2027 ? "simulated" : "observed",
  temperature_mean: 20.3,
  temperature_anomaly: 1.4,
  temperature_sigmas: 1.2,
  temperature_class: "warmer",
  precipitation: 142.3,
  precipitation_ratio: 0.83,
  precipitation_class: "near",
  ...extra,
});

const answer = (years) => ({
  reference_start: "1991-01-01",
  reference_end: "2020-12-31",
  temperature_normal: 18.8,
  temperature_sigma: 1.13,
  precipitation_normal: 171.5,
  years,
});

const empty = {
  temperature_mean: null,
  temperature_anomaly: null,
  temperature_sigmas: null,
  temperature_class: null,
  precipitation: null,
  precipitation_ratio: null,
  precipitation_class: null,
  origin: null,
};

describe("the colour of a tile", () => {
  it("runs blue, green, yellow at the normal, orange, red, and saturates", () => {
    assert.equal(color(-CLAMP), "rgb(33, 102, 172)");
    assert.equal(color(-CLAMP / 2), "rgb(24, 128, 56)");
    assert.equal(color(0), "rgb(242, 197, 61)");
    assert.equal(color(CLAMP / 2), "rgb(240, 124, 30)");
    assert.equal(color(CLAMP), "rgb(198, 40, 40)");
    assert.equal(color(10), color(CLAMP));
  });

  it("writes the year at 4,5:1 at least, everywhere on the scale", () => {
    for (let sigmas = -CLAMP; sigmas <= CLAMP; sigmas += 0.01) {
      const ink = textColor(sigmas) === "#fff" ? [255, 255, 255] : INK;
      assert.ok(contrast(rgb(sigmas), ink) >= 4.5, `${sigmas.toFixed(2)} sigma`);
    }
    // Dark on the normal, white at both ends.
    assert.notEqual(textColor(0), "#fff");
    assert.equal(textColor(-CLAMP), "#fff");
    assert.equal(textColor(CLAMP), "#fff");
  });
});

describe("the tiles", () => {
  it("one per year, the year written on it", () => {
    const made = tiles(answer([year(2025), year(2026, empty), year(2027)]), () => {});
    assert.deepEqual(made.map((tile) => tile.textContent), ["2025", "2026", "2027"]);
  });

  it("cannot click a year without values", () => {
    const [tile] = tiles(answer([year(2026, empty)]), () => {});
    assert.equal(tile.attrs.disabled, "disabled");
    assert.ok(tile.className.includes("none"));
  });

  it("marks the simulated years", () => {
    const [past, future] = tiles(answer([year(2025), year(2027)]), () => {});
    assert.ok(!past.className.includes("simulated"));
    assert.ok(future.className.includes("simulated"));
  });

  it("hands the year clicked to the page", () => {
    let picked = null;
    const [tile] = tiles(answer([year(2047)]), (clicked) => {
      picked = clicked.year;
    });
    tile.dispatchEvent(new Event("click"));
    assert.equal(picked, 2047);
  });
});

describe("the detail", () => {
  it("says the mean, the anomaly and the words of both classes", () => {
    const [temperature, rain] = detail(answer([]), year(2047));
    assert.equal(
      temperature,
      "Température moyenne 20,3 °C, +1,4 °C par rapport à 1991-2020 : plus chaud.",
    );
    assert.equal(rain, "Précipitations 142 mm, 83 % de la normale : proche de la normale.");
  });

  it("signs a negative anomaly", () => {
    assert.equal(signed(-1.6), "-1,6");
  });
});

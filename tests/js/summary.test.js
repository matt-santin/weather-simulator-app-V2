/**
 * The summary card: which figures a season shows, and how they read.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { PICKS, count, figures, heading } from "../../web/static/js/summary.js";

const ANSWER = {
  reference_start: "1991-01-01",
  reference_end: "2020-12-31",
  figures: {
    tasmax_mean: { value: 29.1, normal: 26.7 },
    tas_mean: { value: 22.0, normal: 21.0 },
    hot_35: { value: 12, normal: 1.2 },
    hot_40: { value: 3, normal: 0 },
    tropical_nights: { value: 18, normal: 2.1 },
    summer_days: { value: 70, normal: 55.3 },
    frost_days: { value: 0, normal: 0 },
    precipitation: { value: 186, normal: 252 },
  },
};

describe("summary figures", () => {
  it("shows four figures in summer, in order", () => {
    const shown = figures(ANSWER, "summer");
    assert.deepEqual(shown.map((f) => f.key), PICKS.summer);
    assert.equal(shown[0].value, "+2,4\u00a0°C");
    assert.equal(shown[0].tone, "warm");
    assert.match(shown[1].label, /dont 3 à 40\u00a0°C ou plus/);
    assert.equal(shown[3].value, "-26\u00a0%");
    assert.equal(shown[3].normal, "normale 1991-2020 : 252\u00a0mm");
  });

  it("names the 40 °C days only when there are some", () => {
    const none = { ...ANSWER, figures: { ...ANSWER.figures, hot_40: { value: 0, normal: 0 } } };
    assert.doesNotMatch(figures(none, "summer")[1].label, /40\u00a0°C/);
  });

  it("shows frost and the mean temperature in winter", () => {
    assert.deepEqual(figures(ANSWER, "winter").map((f) => f.key), PICKS.winter);
  });

  it("leaves out a figure with no value", () => {
    const gap = { ...ANSWER, figures: { ...ANSWER.figures, tropical_nights: { value: null, normal: 2 } } };
    assert.equal(figures(gap, "summer").length, 3);
  });
});

describe("count and heading", () => {
  it("writes counts whole or with one decimal", () => {
    assert.equal(count(12), "12");
    assert.equal(count(1.2), "1,2");
  });

  it("names the season, its years and the place", () => {
    assert.equal(heading("summer", "2063-06-21", "2063-09-20", "Lyon"), "Été 2063 à Lyon");
    assert.equal(heading("winter", "2080-12-21", "2081-03-20", "Grenoble"), "Hiver 2080-2081 à Grenoble");
  });
});

/**
 * What the form refuses on its own, before a single request leaves.
 *
 * The API enforces the same three rules and keeps doing so — a limit only the
 * browser applies is not a limit. What is checked here is that the two agree,
 * and that the numbers come from the served config rather than from a constant
 * written into the page.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { refuse } from "../../web/static/js/bounds.js";

/** What GET /api/config really answers. */
const CONFIG = {
  geocoding_url: "https://geocoding-api.open-meteo.com/v1/search",
  coverage_start: "1970-01-01",
  coverage_end: "2100-12-31",
  periods: [
    { start: "1970-01-01", end: "2025-12-31", origin: "observed" },
    { start: "2027-01-01", end: "2100-12-31", origin: "simulated" },
  ],
  max_days: 92,
};

// How long a range is, is `calendar.js` — and so is the daylight-saving trap it
// used to be checked against here. What is left in this file is the refusing.

describe("what the form refuses", () => {
  it("lets an ordinary range through", () => {
    assert.equal(refuse({ start: "2046-07-01", end: "2046-07-14" }, CONFIG), null);
  });

  it("refuses an incomplete range", () => {
    assert.match(refuse({ start: "", end: "2046-07-14" }, CONFIG), /les deux dates/);
    assert.match(refuse({ start: "2046-07-01", end: "" }, CONFIG), /les deux dates/);
  });

  it("refuses a range that runs backwards", () => {
    assert.match(
      refuse({ start: "2046-07-14", end: "2046-07-01" }, CONFIG),
      /précède la date de début/,
    );
  });

  it("refuses a range outside the covered period, at either end", () => {
    assert.match(refuse({ start: "1969-12-31", end: "1970-02-01" }, CONFIG), /1970 à 2100/);
    assert.match(refuse({ start: "2100-12-01", end: "2101-01-01" }, CONFIG), /1970 à 2100/);
  });

  it("refuses a range between the two periods, or straddling one of their ends", () => {
    const unavailable = /Données indisponibles.*1970 à 2025, 2027 à 2100/;
    assert.match(refuse({ start: "2026-07-01", end: "2026-07-14" }, CONFIG), unavailable);
    assert.match(refuse({ start: "2025-12-01", end: "2026-01-31" }, CONFIG), unavailable);
    assert.match(refuse({ start: "2026-12-01", end: "2027-01-31" }, CONFIG), unavailable);
  });

  it("accepts the bounds themselves", () => {
    assert.equal(refuse({ start: "1970-01-01", end: "1970-01-31" }, CONFIG), null);
    assert.equal(refuse({ start: "2025-12-01", end: "2025-12-31" }, CONFIG), null);
    assert.equal(refuse({ start: "2027-01-01", end: "2027-01-31" }, CONFIG), null);
    assert.equal(refuse({ start: "2100-12-01", end: "2100-12-31" }, CONFIG), null);
  });

  it("refuses on the ninety-third day, not on the ninety-second", () => {
    // Ninety-two is the longest season — 21 June to 20 September — and the whole
    // point of the bound is that one fits.
    assert.equal(refuse({ start: "2046-07-01", end: "2046-09-30" }, CONFIG), null);
    assert.match(refuse({ start: "2046-07-01", end: "2046-10-01" }, CONFIG), /93 jours/);
  });

  it("obeys the served max_days, not a 92 written into the page", () => {
    const wider = { ...CONFIG, max_days: 120 };
    assert.equal(refuse({ start: "2046-07-01", end: "2046-10-01" }, wider), null);
    assert.match(refuse({ start: "2046-07-01", end: "2046-11-01" }, wider), /124 jours/);
  });

  it("obeys the served periods too", () => {
    const narrow = { ...CONFIG, periods: [{ start: "2030-01-01", end: "2040-12-31" }] };
    assert.match(refuse({ start: "2046-07-01", end: "2046-07-14" }, narrow), /2030 à 2040/);
  });
});

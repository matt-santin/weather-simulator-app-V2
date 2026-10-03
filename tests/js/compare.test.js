/**
 * The normals, lined up with the days drawn.
 *
 * **The alignment is read off the date, not the index**: a hole in the answer
 * would otherwise push every normal after it out by one, and the two series
 * would be a day apart for three months over a drawing that looks plausible.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { alignByDate, referenceYears } from "../../web/static/js/compare.js";

const day = (date) => ({ date });

describe("the normals of the days drawn", () => {
  it("puts each normal under its own date", () => {
    const days = ["2044-06-21", "2044-06-22", "2044-06-23"].map(day);
    const normals = [
      { date: "2044-06-23", temperature_max: 25 },
      { date: "2044-06-21", temperature_max: 23 },
      { date: "2044-06-22", temperature_max: 24 },
    ];

    const aligned = alignByDate(days, normals);
    assert.deepEqual(
      aligned.map((normal) => normal.temperature_max),
      [23, 24, 25],
    );
  });

  it("leaves a hole where the answer carries no such date", () => {
    const days = ["2048-02-28", "2048-02-29", "2048-03-01"].map(day);
    const normals = [{ date: "2048-02-28" }, { date: "2048-03-01" }];

    const aligned = alignByDate(days, normals);
    assert.deepEqual(
      aligned.map((normal) => normal?.date ?? null),
      ["2048-02-28", null, "2048-03-01"],
    );
  });

  it("names the reference period from the answer", () => {
    const answer = { reference_start: "1991-01-01", reference_end: "2020-12-31" };
    assert.equal(referenceYears(answer), "1991-2020");
  });
});

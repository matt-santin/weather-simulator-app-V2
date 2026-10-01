/**
 * ISO day arithmetic, and the one trap it exists to avoid.
 *
 * Every case here was a comment in three files before it was a test in one:
 * `bounds.js` measured a span, `compare.js` shifted a range, `season.js` walked
 * one, each explaining daylight saving to the next reader. The explanation is
 * now checked rather than repeated — which is what a shared module buys beyond
 * the lines it saves.
 *
 * The dates chosen are the ones where midnight would fail: 2046 changes clocks
 * on 25 March and on 28 October in Europe, and a walk read at midnight there
 * skips or repeats a day.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { DAY, at, eachDay, iso, pad, span } from "../../web/static/js/calendar.js";

describe("how long a range is", () => {
  it("counts both ends", () => {
    assert.equal(span("2046-07-01", "2046-07-01"), 1);
    assert.equal(span("2046-07-01", "2046-07-02"), 2);
    assert.equal(span("2046-07-01", "2046-09-28"), 90);
  });

  it("does not flinch at the daylight-saving change", () => {
    // Read at midnight in a local zone, this range is 23 or 25 hours short of a
    // whole number of days, and the count comes out one too low.
    assert.equal(span("2046-03-24", "2046-03-31"), 8);
    assert.equal(span("2046-10-20", "2046-10-31"), 12);
  });

  it("counts a leap day", () => {
    assert.equal(span("2048-02-01", "2048-03-01"), 30);
    assert.equal(span("2046-02-01", "2046-03-01"), 29);
  });
});

describe("a day and its stamp", () => {
  it("makes the round trip", () => {
    for (const day of ["1950-01-01", "2026-08-17", "2048-02-29", "2050-12-31"]) {
      assert.equal(iso(at(day)), day);
    }
  });

  it("stays on the same day a whole day later", () => {
    assert.equal(iso(at("2046-03-24") + DAY), "2046-03-25");
    assert.equal(iso(at("2046-10-27") + DAY), "2046-10-28");
  });
});

describe("walking a range", () => {
  it("yields both ends and everything between", () => {
    assert.deepEqual(
      [...eachDay("2046-07-01", "2046-07-04")],
      ["2046-07-01", "2046-07-02", "2046-07-03", "2046-07-04"],
    );
  });

  it("yields one day for a range of one", () => {
    assert.deepEqual([...eachDay("2046-07-01", "2046-07-01")], ["2046-07-01"]);
  });

  it("crosses a daylight-saving change without skipping or repeating", () => {
    const walked = [...eachDay("2046-03-24", "2046-03-27")];
    assert.deepEqual(walked, ["2046-03-24", "2046-03-25", "2046-03-26", "2046-03-27"]);
    assert.equal(new Set(walked).size, walked.length);
  });

  it("crosses a leap day", () => {
    assert.deepEqual(
      [...eachDay("2048-02-28", "2048-03-01")],
      ["2048-02-28", "2048-02-29", "2048-03-01"],
    );
  });

  it("yields as many days as the span it was given", () => {
    // The two readings of one range, which is what keeps the form's count and
    // the results page's ground from ever disagreeing.
    for (const [start, end] of [
      ["2046-07-01", "2046-09-30"],
      ["2046-03-24", "2046-03-31"],
      ["2049-12-21", "2050-03-20"],
    ]) {
      assert.equal([...eachDay(start, end)].length, span(start, end));
    }
  });

  it("yields nothing for a range that is not one", () => {
    assert.deepEqual([...eachDay("", "2046-07-04")], []);
    assert.deepEqual([...eachDay("2046-07-04", "")], []);
    assert.deepEqual([...eachDay("2046-07-04", "2046-07-01")], []);
  });
});

describe("two digits", () => {
  it("pads what needs it and leaves the rest", () => {
    assert.equal(pad(1), "01");
    assert.equal(pad(9), "09");
    assert.equal(pad(10), "10");
    assert.equal(pad(12), "12");
  });
});

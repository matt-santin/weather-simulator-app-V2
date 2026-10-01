/**
 * The dates of the compared year, and how its days line up with the ones drawn.
 *
 * Three things are checked rather than described. **The 29th of February**, which
 * is the only date the shift can fail on, and it fails silently — JavaScript
 * slides an impossible date to the next month instead of refusing it. **The day
 * the shift can gain**, which would hand the API a range one longer than it
 * accepts. And **the alignment**, which has to be read off the calendar rather
 * than off the index, since a hole in one year would otherwise push every day
 * after it out by one — the two curves would then be a day apart for three
 * months, over a series that looks perfectly plausible.
 *
 * **The round trip is the test that matters most**, in the same spirit as
 * `season.test.js`: shift a range to a year and read the year back, and it must
 * be the one asked for.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  ORDINARY_YEAR,
  alignByCalendar,
  selectableYears,
  shiftRange,
} from "../../web/static/js/compare.js";

/** What GET /api/config really answers, of the part this module reads. */
const CONFIG = {
  periods: [
    { start: "1970-01-01", end: "2005-12-31", origin: "observed" },
    { start: "2027-01-01", end: "2100-12-31", origin: "simulated" },
  ],
  max_days: 92,
};

/** A day of the contract, of the two fields this module touches. */
const day = (date, origin = "observed") => ({ date, origin });

const dates = (days) => days.map((found) => found?.date ?? null);

describe("the same dates in another year", () => {
  it("moves both ends and keeps the shape of the range", () => {
    const shifted = shiftRange({ start: "2046-06-21", end: "2046-09-20" }, 1991, 92);
    assert.deepEqual(shifted, { start: "1991-06-21", end: "1991-09-20" });
  });

  it("carries a range that spans two calendar years", () => {
    // A winter opens in December and closes in March. Putting both ends in the
    // same year would ask for a range running backwards.
    const shifted = shiftRange({ start: "2046-12-21", end: "2047-03-20" }, 1991, 92);
    assert.deepEqual(shifted, { start: "1991-12-21", end: "1992-03-20" });
  });

  it("stands the eve in for a 29th of February that does not exist", () => {
    // Date.parse("1991-02-29") does not throw: it answers 1 March. Left
    // unchecked, the range would quietly start on the wrong day.
    const shifted = shiftRange({ start: "2048-02-29", end: "2048-04-30" }, 1991, 92);
    assert.equal(shifted.start, "1991-02-28");
  });

  it("keeps the 29th when the year it lands in has one", () => {
    const shifted = shiftRange({ start: "2048-02-29", end: "2048-04-30" }, 1992, 92);
    assert.equal(shifted.start, "1992-02-29");
  });

  it("trims the day a leap year would add", () => {
    // 1 February to 3 May is 92 days in a common year and 93 in a leap one.
    // Ninety-three is one more than the API accepts, so the end gives way.
    const asked = { start: "2046-02-01", end: "2046-05-03" };
    const shifted = shiftRange(asked, 1992, 92);
    assert.equal(shifted.start, "1992-02-01");
    assert.equal(shifted.end, "1992-05-02");
  });

  it("leaves a range short rather than stretching it", () => {
    // The other direction: a leap range shifted onto a common year loses its
    // 29th and comes back one day shorter. Nothing is invented to fill it.
    const shifted = shiftRange({ start: "2048-02-01", end: "2048-05-02" }, 1991, 92);
    assert.deepEqual(shifted, { start: "1991-02-01", end: "1991-05-02" });
  });

  it("comes back with the year it was asked for", () => {
    // The round trip. Four seasons, both the wrapping one and the three that
    // do not, plus the range that straddles a 29th of February.
    const ranges = [
      { start: "2046-03-21", end: "2046-06-20" },
      { start: "2046-06-21", end: "2046-09-20" },
      { start: "2046-09-21", end: "2046-12-20" },
      { start: "2046-12-21", end: "2047-03-20" },
      { start: "2048-02-01", end: "2048-05-02" },
    ];
    for (const range of ranges) {
      for (const year of [1950, 1991, 1992, 2024]) {
        const shifted = shiftRange(range, year, 92);
        assert.equal(Number(shifted.start.slice(0, 4)), year, `${range.start} → ${year}`);
        assert.ok(shifted.start <= shifted.end);
        assert.ok(span(shifted) <= 92);
      }
    }
  });
});

/** Both ends counted, written here so the assertion above says what it means. */
function span({ start, end }) {
  const DAY = 24 * 60 * 60 * 1000;
  return Math.round((Date.parse(`${end}T12:00:00Z`) - Date.parse(`${start}T12:00:00Z`)) / DAY) + 1;
}

describe("laying one year alongside the other", () => {
  it("matches on the month and the day, not on the position", () => {
    const days = [day("2046-07-01"), day("2046-07-02"), day("2046-07-03")];
    // The compared series starts a day later than the range asked for, which is
    // what the API does when its first day is not the one requested.
    const compared = [day("1991-07-02"), day("1991-07-03")];

    assert.deepEqual(dates(alignByCalendar(days, compared)), [
      null,
      "1991-07-02",
      "1991-07-03",
    ]);
  });

  it("leaves a hole where the compared year has no such day", () => {
    const days = [day("2048-02-28"), day("2048-02-29"), day("2048-03-01")];
    const compared = [day("1991-02-28"), day("1991-03-01")];

    // The 29th keeps its slot and stays empty; the 1st of March is not pulled
    // back into it. An index alignment would have shifted both by one.
    assert.deepEqual(dates(alignByCalendar(days, compared)), [
      "1991-02-28",
      null,
      "1991-03-01",
    ]);
  });

  it("answers one slot per day drawn, always", () => {
    const days = [day("2046-07-01"), day("2046-07-02")];
    assert.equal(alignByCalendar(days, []).length, 2);
    assert.deepEqual(alignByCalendar(days, []), [null, null]);
  });

  it("drops a day that is not observed", () => {
    // The menu only offers observed years. If it did not, this is what keeps a
    // simulated day from being drawn as the old climate.
    const days = [day("2046-07-01"), day("2046-07-02")];
    const compared = [day("2005-07-01"), day("2005-07-02", "simulated")];

    assert.deepEqual(dates(alignByCalendar(days, compared)), ["2005-07-01", null]);
  });
});

describe("the years the menu may offer", () => {
  const summer = { start: "2046-06-21", end: "2046-09-20" };

  it("offers the observed years, and those only", () => {
    const years = selectableYears(summer, CONFIG);
    assert.equal(years[0], 1970);
    assert.equal(years.at(-1), 2005);
    assert.equal(years.length, 36);
  });

  it("withholds a year whose shifted range leaves the observed period", () => {
    const winter = { start: "2046-12-21", end: "2047-03-20" };
    assert.equal(selectableYears(winter, CONFIG).at(-1), 2004);
  });

  it("holds the measured default", () => {
    // Not a taste: 1980 sits at −2,00 σ in summer and 2003 at +3,25 σ, either
    // of which would show about as much artificial gap as there is signal.
    assert.equal(ORDINARY_YEAR, 1991);
    assert.ok(selectableYears(summer, CONFIG).includes(ORDINARY_YEAR));
  });
});

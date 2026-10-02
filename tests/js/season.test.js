/**
 * Which ground a search lands on, and which dates a season asked for by name is.
 *
 * Three decisions are checked here rather than described: the astronomical
 * bounds and their eve, the season the count settles on when a range straddles
 * two, and the reversal below the equator. A third candidate is reachable since
 * the bound went to ninety-two, and was reachable by a hand-typed URL before
 * that, so the three-season range is checked either way.
 *
 * **The round trip is the test that matters most here.** `rangeOf` and
 * `seasonOf` read one table in opposite directions, and the day they disagree is
 * the day the form asks for a summer and the results page paints a winter. It is
 * checked on all four seasons and both hemispheres.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { dominantSeason, rangeOf, seasonOf, yearsFor } from "../../web/static/js/season.js";

/** What GET /api/config really answers, of the part this module reads. */
const CONFIG = {
  coverage_start: "1970-01-01",
  coverage_end: "2100-12-31",
  periods: [
    { start: "1970-01-01", end: "2025-12-31", origin: "observed" },
    { start: "2027-01-01", end: "2100-12-31", origin: "simulated" },
  ],
};

const NAMES = ["winter", "spring", "summer", "autumn"];

/** Northern unless a latitude says otherwise. */
const north = { latitude: 48.8566 }; // Paris
const south = { latitude: -33.4489 }; // Santiago

describe("the season of one day", () => {
  it("turns on the twenty-first, not on the twentieth", () => {
    assert.equal(seasonOf("2046-03-20"), "winter");
    assert.equal(seasonOf("2046-03-21"), "spring");
    assert.equal(seasonOf("2046-06-20"), "spring");
    assert.equal(seasonOf("2046-06-21"), "summer");
    assert.equal(seasonOf("2046-09-20"), "summer");
    assert.equal(seasonOf("2046-09-21"), "autumn");
    assert.equal(seasonOf("2046-12-20"), "autumn");
    assert.equal(seasonOf("2046-12-21"), "winter");
  });

  it("carries December's winter into January", () => {
    assert.equal(seasonOf("2046-12-31"), "winter");
    assert.equal(seasonOf("2046-01-01"), "winter");
  });

  it("reverses below the equator", () => {
    assert.equal(seasonOf("2046-01-15", south.latitude), "summer");
    assert.equal(seasonOf("2046-07-14", south.latitude), "winter");
    assert.equal(seasonOf("2046-04-01", south.latitude), "autumn");
    assert.equal(seasonOf("2046-10-01", south.latitude), "spring");
  });

  it("reads a latitude it cannot use as northern", () => {
    // A hand-edited URL gives NaN, and NaN < 0 is false. The calendar is the
    // right answer to give there, not an error.
    assert.equal(seasonOf("2046-01-15", Number("")), "winter");
    assert.equal(seasonOf("2046-01-15", undefined), "winter");
    // The equator itself counts as northern, which is a choice and not a
    // measurement: at 0° neither season means much.
    assert.equal(seasonOf("2046-01-15", 0), "winter");
  });
});

describe("the season a range belongs to", () => {
  it("takes the season a range sits inside", () => {
    assert.equal(dominantSeason({ start: "2046-07-01", end: "2046-07-14", ...north }), "summer");
    assert.equal(dominantSeason({ start: "2046-01-05", end: "2046-02-20", ...north }), "winter");
  });

  it("takes the better represented of two — the documented example", () => {
    // 1 June to 1 August: twenty days of spring, forty-two of summer.
    assert.equal(dominantSeason({ start: "2046-06-01", end: "2046-08-01", ...north }), "summer");
  });

  it("counts rather than looks at either end", () => {
    // Starts in winter, ends in spring, and is winter all the same: 69 to 21.
    assert.equal(dominantSeason({ start: "2046-01-11", end: "2046-04-10", ...north }), "winter");
  });

  it("gives a tie to the season the range ends in", () => {
    // Ten days of summer, then ten of autumn.
    assert.equal(dominantSeason({ start: "2046-09-11", end: "2046-09-30", ...north }), "autumn");
    // And the other way round, so the rule is not the alphabet.
    assert.equal(dominantSeason({ start: "2046-06-11", end: "2046-06-30", ...north }), "summer");
  });

  it("crosses the new year", () => {
    assert.equal(dominantSeason({ start: "2045-12-21", end: "2046-01-10", ...north }), "winter");
    assert.equal(dominantSeason({ start: "2045-12-01", end: "2046-01-15", ...north }), "winter");
  });

  it("does not flinch at the daylight-saving change", () => {
    // The walk steps by exact days at noon UTC. Read at local midnight, these
    // ranges lose or repeat a day, and a count is what this file is.
    assert.equal(dominantSeason({ start: "2046-03-21", end: "2046-03-31", ...north }), "spring");
    assert.equal(dominantSeason({ start: "2046-10-20", end: "2046-10-31", ...north }), "autumn");
  });

  it("reverses below the equator", () => {
    assert.equal(dominantSeason({ start: "2046-01-05", end: "2046-02-20", ...south }), "summer");
    assert.equal(dominantSeason({ start: "2046-06-01", end: "2046-08-01", ...south }), "winter");
  });

  it("still answers on a range longer than any search", () => {
    // Nine months, which no form offers. The count holds all the same: 92
    // summer, 91 autumn, 90 winter. A shorter three-season range *is* now
    // reachable — a day of autumn, a whole winter, a day of spring is 92 — and
    // the same tally settles that one.
    assert.equal(dominantSeason({ start: "2046-06-21", end: "2047-03-20", ...north }), "summer");
  });

  it("has nothing to say about a range that is not one", () => {
    // Null rather than a season invented: the page keeps the ground its markup
    // already carries, and the refusal is drawn on it.
    assert.equal(dominantSeason({ start: "", end: "2046-07-14", ...north }), null);
    assert.equal(dominantSeason({ start: "2046-07-14", end: "", ...north }), null);
    assert.equal(dominantSeason({ start: "2046-07-14", end: "2046-07-01", ...north }), null);
    assert.equal(dominantSeason({ start: "avant", end: "hier", ...north }), null);
  });
});

describe("the dates one season covers", () => {
  it("opens on the twenty-first and closes on the eve of the next", () => {
    assert.deepEqual(rangeOf("spring", 2029, north.latitude), {
      start: "2029-03-21",
      end: "2029-06-20",
    });
    assert.deepEqual(rangeOf("summer", 2029, north.latitude), {
      start: "2029-06-21",
      end: "2029-09-20",
    });
    assert.deepEqual(rangeOf("autumn", 2029, north.latitude), {
      start: "2029-09-21",
      end: "2029-12-20",
    });
  });

  it("gives winter the year it begins in, not the one it ends in", () => {
    // The only season in two calendar years, and the only place the rule shows.
    // "Hiver 2029" is the one that opens in December 2029.
    assert.deepEqual(rangeOf("winter", 2029, north.latitude), {
      start: "2029-12-21",
      end: "2030-03-20",
    });
  });

  it("is no longer than the bound the API serves", () => {
    // Ninety-two, which is why MAX_DAYS is ninety-two. Counted both ends, as
    // bounds.js counts, and on a leap winter for the one that could exceed it.
    const length = ({ start, end }) =>
      Math.round((Date.parse(`${end}T12:00:00Z`) - Date.parse(`${start}T12:00:00Z`)) / 86_400_000) +
      1;
    for (const name of NAMES) {
      for (const year of [2029, 2031]) {
        assert.ok(length(rangeOf(name, year, north.latitude)) <= 92);
      }
    }
    assert.equal(length(rangeOf("winter", 2027, north.latitude)), 91); // ends in a leap year
    assert.equal(length(rangeOf("summer", 2029, north.latitude)), 92);
  });

  it("gives the place its own season below the equator", () => {
    // Not the calendar's: a summer asked for in Santiago is December to March.
    assert.deepEqual(rangeOf("summer", 2029, south.latitude), {
      start: "2029-12-21",
      end: "2030-03-20",
    });
    assert.deepEqual(rangeOf("winter", 2029, south.latitude), {
      start: "2029-06-21",
      end: "2029-09-20",
    });
  });

  it("closes the circle with seasonOf, on both hemispheres", () => {
    // The one property this file exists to hold: ask for a season, and every day
    // of what comes back reads as that season. Otherwise the form asks for a
    // summer and the results page paints a winter.
    for (const latitude of [north.latitude, south.latitude]) {
      for (const name of NAMES) {
        const range = rangeOf(name, 2029, latitude);
        assert.equal(seasonOf(range.start, latitude), name);
        assert.equal(seasonOf(range.end, latitude), name);
        assert.equal(dominantSeason({ ...range, latitude }), name);
      }
    }
  });

  it("keeps every boundary late enough in its month for the eve to be simple", () => {
    // rangeOf takes a season's last day to be the day before the next one opens,
    // and reads it as "the same month, one lower". Move a boundary to the 1st
    // and that yields a zeroth day, silently.
    for (const name of NAMES) {
      assert.ok(Number(rangeOf(name, 2029, north.latitude).end.slice(8, 10)) >= 1);
    }
  });

  it("has nothing to hand back for something that is not a season", () => {
    assert.equal(rangeOf("canicule", 2029, north.latitude), null);
    assert.equal(rangeOf("summer", Number.NaN, north.latitude), null);
  });
});

describe("the years a season can be asked for", () => {
  it("offers every year of both periods to the three that stay inside one", () => {
    for (const name of ["spring", "summer", "autumn"]) {
      const years = yearsFor(name, north.latitude, CONFIG);
      assert.equal(years.at(0), 1970);
      assert.equal(years.at(-1), 2100);
      assert.ok(years.includes(2025) && years.includes(2027));
      assert.ok(!years.includes(2026));
      assert.equal(years.length, 56 + 74);
    }
  });

  it("withholds from winter the years whose far end falls outside a period", () => {
    // Winter 2025 ends on 20 March 2026, winter 2100 on 20 March 2101: offering
    // them would be offering a refusal.
    const years = yearsFor("winter", north.latitude, CONFIG);
    assert.ok(years.includes(2024) && !years.includes(2025));
    assert.equal(years.at(-1), 2099);
  });

  it("withholds them from summer below the equator, being the same three months", () => {
    assert.equal(yearsFor("summer", south.latitude, CONFIG).at(-1), 2099);
    assert.equal(yearsFor("winter", south.latitude, CONFIG).at(-1), 2100);
  });

  it("reads the periods it is served rather than periods written here", () => {
    const narrow = { periods: [{ start: "2030-01-01", end: "2040-12-31" }] };
    assert.deepEqual(yearsFor("summer", north.latitude, narrow).at(0), 2030);
    assert.deepEqual(yearsFor("summer", north.latitude, narrow).at(-1), 2040);
  });
});

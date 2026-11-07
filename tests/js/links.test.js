import assert from "node:assert/strict";
import { test } from "node:test";

import { insideMap, mapHref, resultsHref, seasonOfDay, seasonYear } from "../../web/static/js/links.js";

const BOX = { west: -25, east: 45, south: 34, north: 72 };

test("a season's year is the one its dates open in", () => {
  assert.equal(seasonYear("summer", "2063-06-21", "2063-09-20"), 2063);
  assert.equal(seasonYear("winter", "2080-12-21", "2081-03-20"), 2080);
  // A part of a winter, in January: the winter that opened the December before.
  assert.equal(seasonYear("winter", "2081-01-05", "2081-02-10"), 2080);
});

test("a range outside its season has no year", () => {
  assert.equal(seasonYear("summer", "2063-01-01", "2063-02-01"), null);
});

test("the map shows the places inside its frame only", () => {
  assert.ok(insideMap(BOX, 45.75, 4.85));
  assert.ok(!insideMap(BOX, 33.9, 4.85));
  assert.ok(!insideMap(BOX, 45.75, 46));
  assert.ok(!insideMap(null, 45.75, 4.85));
});

test("results and map send each other the same season at the same place", () => {
  const asked = { season: "winter", year: 2080, place: "Grenoble", latitude: 45.178712, longitude: 5.714791 };
  const map = new URL(mapHref(asked), "http://x");
  assert.equal(map.pathname, "/cartes");
  assert.deepEqual(Object.fromEntries(map.searchParams), {
    grandeur: "tasmax", saison: "winter", annee: "2080", lieu: "Grenoble", lat: "45.1787", lon: "5.7148",
  });
  const results = new URL(resultsHref(asked), "http://x");
  assert.equal(results.pathname, "/resultats");
  assert.deepEqual(Object.fromEntries(results.searchParams), {
    lieu: "Grenoble", lat: "45.1787", lon: "5.7148", debut: "2080-12-21", fin: "2081-03-20",
  });
  const back = Object.fromEntries(results.searchParams);
  assert.equal(seasonYear("winter", back.debut, back.fin), 2080);
});

test("a day is in the season of the map that holds it", () => {
  assert.deepEqual(seasonOfDay("2063-07-14"), { season: "summer", year: 2063 });
  assert.deepEqual(seasonOfDay("2081-01-10"), { season: "winter", year: 2080 });
  assert.deepEqual(seasonOfDay("2080-12-25"), { season: "winter", year: 2080 });
});

test("a day travels with the season, when the season holds it", () => {
  const asked = { season: "summer", year: 2063, place: "Lyon", latitude: 45.75, longitude: 4.85 };
  const map = new URL(mapHref({ ...asked, day: "2063-07-14" }), "http://x");
  assert.equal(map.searchParams.get("jour"), "2063-07-14");
  const results = new URL(resultsHref({ ...asked, day: "2063-07-14" }), "http://x");
  assert.equal(results.searchParams.get("jour"), "2063-07-14");
  const outside = new URL(resultsHref({ ...asked, day: "2063-12-01" }), "http://x");
  assert.equal(outside.searchParams.get("jour"), null);
  assert.equal(new URL(mapHref(asked), "http://x").searchParams.get("jour"), null);
});

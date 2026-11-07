/**
 * The way between the results page and the map page: the address of one built
 * from what the other shows. No DOM, no fetching: `node --test` checks it.
 *
 * What travels is a place (name, latitude, longitude), a season and a year,
 * and a day of it (`jour`) when the visitor moves from one day to the same day.
 * The results page reads dates (`debut`, `fin`), the map a season and a year
 * (`saison`, `annee`): one is turned into the other with season.js, so that
 * both pages agree on what "été 2063" is.
 */

import { rangeOf, seasonOf } from "./season.js";

/** The map page reads its seasons at this latitude: Europe is northern. */
export const MAP_LATITUDE = 50;

/**
 * The year of `season` a range falls in: the one whose dates hold the middle of
 * the range. A winter is the year it opens in (December 2080 to March 2081 is
 * 2080), as rangeOf says. Null when neither candidate holds it.
 */
export function seasonYear(season, start, end) {
  const middle = new Date((Date.parse(start) + Date.parse(end)) / 2).toISOString().slice(0, 10);
  const first = Number(start.slice(0, 4));
  for (const year of [first, first - 1, first + 1]) {
    const range = rangeOf(season, year, MAP_LATITUDE);
    if (range && range.start <= middle && middle <= range.end) return year;
  }
  return null;
}

/** The season and year of the map that hold a day: { season, year }. */
export function seasonOfDay(day) {
  const season = seasonOf(day, MAP_LATITUDE);
  return { season, year: seasonYear(season, day, day) };
}

/** Whether a point is inside the frame of the map (`map_box` of /api/config). */
export function insideMap(box, latitude, longitude) {
  return Boolean(box) &&
    latitude >= box.south && latitude <= box.north &&
    longitude >= box.west && longitude <= box.east;
}

/** Coordinates as they travel in an address: four decimals, about 10 m. */
const coordinate = (value) => String(Math.round(value * 1e4) / 1e4);

/** The map of a season, with a place marked on it. */
export function mapHref({ season, year, place, latitude, longitude, day = null, variable = "tasmax" }) {
  const query = new URLSearchParams({
    grandeur: variable,
    saison: season,
    annee: String(year),
    lieu: place,
    lat: coordinate(latitude),
    lon: coordinate(longitude),
  });
  if (day) query.set("jour", day);
  return `/cartes?${query}`;
}

/** The results of a season at a place. */
export function resultsHref({ season, year, place, latitude, longitude, day = null }) {
  const range = rangeOf(season, year, MAP_LATITUDE);
  const query = new URLSearchParams({
    lieu: place,
    lat: coordinate(latitude),
    lon: coordinate(longitude),
    debut: range.start,
    fin: range.end,
  });
  if (day && range.start <= day && day <= range.end) query.set("jour", day);
  return `/resultats?${query}`;
}

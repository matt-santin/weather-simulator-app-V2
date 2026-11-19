/**
 * "À voir aussi", at the foot of the results page (19/11/2026): four other
 * pages, chosen for the page shown. No DOM, no fetching: `node --test` checks it.
 *
 * 1. The next season, same place (the previous one when the next is not served).
 * 2. A typical season of another period: for a simulated season, the year of
 *    1991-2020 whose mean of the daily maximum is nearest the mean of the 30
 *    years; for an observed one, the same in 2071-2100.
 * 3. The record here: the hottest season of the future climate (the coldest of
 *    the old climate in winter), or its extreme day when the page shows that
 *    record already.
 * 4. The same dates in a large city of another climate (/api/contrast).
 *
 * The criterion is the one of the kinds and of the rank (/api/kinds `values`):
 * the mean of the daily maximum over the dates of the season. Choices of the
 * project (19/11/2026), not a norm.
 */

import { texts } from "./i18n.js";
import { kindLabels } from "./kinds.js";

const ORDER = ["spring", "summer", "autumn", "winter"];

/** The season after `season` of `year` (a winter is the year it opens in). */
export function nextSeason(season, year) {
  const k = ORDER.indexOf(season);
  if (k < 0) return null;
  return k === ORDER.length - 1 ? { season: ORDER[0], year: year + 1 } : { season: ORDER[k + 1], year };
}

/** The season before `season` of `year`. */
export function previousSeason(season, year) {
  const k = ORDER.indexOf(season);
  if (k < 0) return null;
  return k === 0 ? { season: ORDER[ORDER.length - 1], year: year - 1 } : { season: ORDER[k - 1], year };
}

/** The periods of the typical season: one is compared with the other. */
export const TYPICAL = { observed: [1991, 2020], simulated: [2071, 2100] };

/** Every year and value of the epochs of /api/kinds, in one object. */
export function allValues(kinds) {
  const out = {};
  for (const epoch of kinds?.epochs ?? []) Object.assign(out, epoch.values ?? {});
  return out;
}

/**
 * The typical season of `first`-`last`: the year whose value is nearest the
 * mean of the period (the later one on a tie), never `shown`. `{ year, value,
 * mean }`, or null when the period has fewer than 20 values.
 */
export function typical(values, first, last, shown = null) {
  const years = Object.keys(values).map(Number).filter((y) => y >= first && y <= last);
  if (years.length < 20) return null;
  const mean = years.reduce((sum, y) => sum + values[y], 0) / years.length;
  let best = null;
  for (const year of years) {
    if (year === shown) continue;
    const gap = Math.abs(values[year] - mean);
    if (best === null || gap <= best.gap) best = { year, gap };
  }
  return best && { year: best.year, value: values[best.year], mean };
}

/**
 * Which period the typical season is taken from: 2071-2100 for an observed
 * season, 1991-2020 for a simulated one. `observed` says which the page shows.
 */
export function typicalSpan(observed) {
  return observed ? TYPICAL.simulated : TYPICAL.observed;
}

/**
 * The record of card 3: `{ kind, epoch, year, day, value }`. Out of winter, the
 * hottest season of the future climate, or its hottest day when the page
 * already shows that season; in winter, the coldest of the old climate, or its
 * coldest night. `shownKind` is `type` of the address, `shownYear` the year of
 * the season shown. Null without the epoch or its values.
 */
export function recordPick(kinds, season, shownYear, shownKind = null) {
  const winter = season === "winter";
  const epoch = (kinds?.epochs ?? []).find((e) => e.id === (winter ? "old" : "future"));
  if (!epoch) return null;
  const sign = winter ? -1 : 1;
  const seasonKind = winter ? "coldRecord" : "record";
  const dayKind = winter ? "coldestDay" : "hottestDay";
  const peak = winter ? epoch.coldest : epoch.hottest;
  let year = null;
  let value = null;
  for (const [y, v] of Object.entries(epoch.values ?? {})) {
    if (year === null || sign * v >= sign * value) {
      year = Number(y);
      value = v;
    }
  }
  if (year === null) return null;
  if (shownYear === year) {
    // The record is on screen: its extreme day, unless that is on screen too.
    if (!peak || shownKind === dayKind) return null;
    return { kind: dayKind, epoch: epoch.id, year: peak.year, day: peak.date, value: peak.value };
  }
  return { kind: seasonKind, epoch: epoch.id, year, day: null, value };
}

const ONE = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** A temperature as the cards write it: "26,6 °C". */
export function degrees(value) {
  return `${ONE.format(value)} °C`;
}

/**
 * The record card in words: `{ kicker, line }`. "Record de chaleur du climat
 * futur", "Maximales : 33,1 °C en moyenne"; "Jour le plus chaud du climat
 * futur", "Maximale : 45,6 °C".
 */
export function recordWords(pick, season) {
  const w = texts.suggest;
  const day = pick.kind === "hottestDay" || pick.kind === "coldestDay";
  return {
    kicker: `${kindLabels(season)[pick.kind]} ${texts.summary.epochOf[pick.epoch]}`,
    line: day
      ? (pick.kind === "coldestDay" ? w.minimum : w.maximum)(degrees(pick.value))
      : w.meanMaximum(degrees(pick.value)),
  };
}

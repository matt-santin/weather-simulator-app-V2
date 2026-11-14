/**
 * A cool, normal or warm season of an epoch, drawn at random, or its record.
 *
 * The server ranks the years of each epoch (`/api/kinds`, src/app/api/kinds.py);
 * this file only names the kinds and draws one year among those of the kind
 * asked for. The records (7/11/2026) are no draw: the season of the epoch with the
 * highest, or the lowest, mean of the daily maximum, the criterion of the
 * ranking, read in the `values` the server sends. No DOM, no fetching: `node --test` checks it.
 */

import { texts } from "./i18n.js";

// In the order of the scale, from the coldest record to the hottest.
export const KINDS = ["coldRecord", "cool", "normal", "warm", "record"];

/**
 * The kinds a season offers: the five above, then its extreme day: the hottest
 * day in spring, summer and autumn, the coldest night in winter (7/11/2026).
 */
export function kindsOf(season) {
  return [...KINDS, season === "winter" ? "coldestDay" : "hottestDay"];
}

/** The peak of the epoch a day kind asks for, or null for the other kinds. */
function peakOf(ranked, kind) {
  if (kind === "hottestDay") return ranked?.hottest ?? null;
  if (kind === "coldestDay") return ranked?.coldest ?? null;
  return null;
}

/** The day a kind leads to (the extreme day), or null: the season opens on it. */
export function dayOf(ranked, kind) {
  return peakOf(ranked, kind)?.date ?? null;
}

/** The words of the kinds: a winter is cold or mild, not cool or warm. */
export function kindLabels(season) {
  return season === "winter" ? texts.form.kindsWinter : texts.form.kinds;
}

/** What the epoch is called in the list, with its years. */
export function epochLabel(epoch) {
  return texts.form.epochOption(texts.form.epochs[epoch.id] ?? epoch.id, epoch.first, epoch.last);
}

/**
 * The year a season is asked for in, to query `/api/kinds`: the first one of
 * the epoch that `yearsFor` offers. Any year of the epoch would do, the server
 * shifts the dates to every other; it only has to be a served one.
 */
export function anyYearOf(epoch, years) {
  return years.find((year) => year >= epoch.first && year <= epoch.last) ?? null;
}

/**
 * The record of an epoch: the year of the highest value (`sign` 1) or of the
 * lowest (`sign` -1), the later one on a tie. Null when there is no value.
 */
export function record(ranked, sign = 1) {
  let best = null;
  for (const [year, value] of Object.entries(ranked?.values ?? {})) {
    if (best === null || sign * value >= sign * best.value) best = { year: Number(year), value };
  }
  return best?.year ?? null;
}

/**
 * One year of `ranked[kind]`, or null if there is none. `random` is in [0, 1).
 * The record is not drawn: it is the one year.
 */
/** The kinds whose year is drawn at random: the others always give the same one. */
export const DRAWN = ["cool", "normal", "warm"];

/**
 * Another year of the same kind than `shown`, or null when there is none: the
 * kind has one year only, or always gives the same (a record, an extreme day).
 */
export function drawAnother(ranked, kind, shown, random = Math.random) {
  if (!DRAWN.includes(kind)) return null;
  const others = (ranked?.[kind] ?? []).filter((year) => year !== shown);
  if (others.length === 0) return null;
  return others[Math.min(others.length - 1, Math.floor(random() * others.length))];
}

export function draw(ranked, kind, random = Math.random) {
  if (kind === "hottestDay" || kind === "coldestDay") return peakOf(ranked, kind)?.year ?? null;
  if (kind === "record") return record(ranked, 1);
  if (kind === "coldRecord") return record(ranked, -1);
  const years = ranked?.[kind] ?? [];
  if (years.length === 0) return null;
  return years[Math.min(years.length - 1, Math.floor(random() * years.length))];
}

/**
 * A cool, normal or warm season of an epoch, drawn at random.
 *
 * The server ranks the years of each epoch (`/api/kinds`, src/app/api/kinds.py);
 * this file only names the three kinds and draws one year among those of the
 * kind asked for. No DOM, no fetching: `node --test` checks it.
 */

import { texts } from "./i18n.js";

export const KINDS = ["cool", "normal", "warm"];

/** The words of the three kinds: a winter is cold or mild, not cool or warm. */
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

/** One year of `ranked[kind]`, or null if there is none. `random` is in [0, 1). */
export function draw(ranked, kind, random = Math.random) {
  const years = ranked?.[kind] ?? [];
  if (years.length === 0) return null;
  return years[Math.min(years.length - 1, Math.floor(random() * years.length))];
}

/**
 * The summary card of the results page: which figures a season shows, and how
 * each is written. No DOM, no fetching: `node --test` checks it.
 *
 * The server computes every figure (/api/summary, src/app/api/summary.py); the
 * season picks four at most (decided 5/11/2026):
 *
 * - summer: mean maximum, days at 35 °C or more (and at 40 °C, when there are
 *   any), tropical nights, rain;
 * - winter: mean temperature, frost days, rain;
 * - spring and autumn: mean maximum, days above 25 °C, frost days, rain.
 */

import { texts } from "./i18n.js";

const ONE = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const SIGNED = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

const PERCENT = new Intl.NumberFormat("fr-FR", { signDisplay: "exceptZero" });

export const PICKS = {
  summer: ["tasmax_mean", "hot_35", "tropical_nights", "precipitation"],
  winter: ["tas_mean", "frost_days", "precipitation"],
  spring: ["tasmax_mean", "summer_days", "frost_days", "precipitation"],
  autumn: ["tasmax_mean", "summer_days", "frost_days", "precipitation"],
};

/** A count: whole when it is, one decimal for a normal (a mean of 30 years). */
export function count(value) {
  return Number.isInteger(value) ? String(value) : ONE.format(value);
}

/** The heading: "Été 2063 à Lyon", "Hiver 2080-2081 à Grenoble". */
export function heading(season, start, end, place) {
  const first = start.slice(0, 4);
  const last = end.slice(0, 4);
  const years = first === last ? first : `${first}-${last}`;
  return texts.summary.heading(texts.season[season] ?? "", years, place);
}

/**
 * Where the dates shown stand among the observed years, in a sentence, from the
 * `rank` of /api/summary: "Plus chaud que les 56 étés observés de 1970 à 2025.",
 * "Seuls 2 étés observés de 1970 à 2025 ont été plus chauds : 2003, 2022.",
 * "Plus frais que 41 des 56 étés observés de 1970 à 2025." The warm side is told
 * while fewer than half of the observed years were warmer, the cool one after.
 * `observed` says the season shown is itself one of the observed years: the
 * others are then "les autres". Empty without a rank.
 */
export function standing(rank, season, observed = false) {
  const words = texts.summary;
  const names = words.seasons[season];
  if (!rank || !names || rank.total === 0) return "";
  const [singular, plural] = names;
  const span = words.rankSpan(rank.first, rank.last);
  const { total, warmer } = rank;
  if (warmer === 0) return words.rankAll(words.warm[season], total, plural, span, observed);
  if (warmer === total) return words.rankAll(words.cool[season], total, plural, span, observed);
  if (warmer <= rank.warmer_years.length) {
    return words.rankFew(
      warmer, singular, plural, words.warm[season], words.warmPlural[season], span,
      rank.warmer_years.join(", "),
    );
  }
  if (warmer * 2 < total) return words.rankMost(words.warm[season], total - warmer, total, plural, span, observed);
  return words.rankMost(words.cool[season], warmer, total, plural, span, observed);
}

/**
 * The figures of `answer` (/api/summary) the season shows, each as
 * `{ key, value, label, normal, tone }`; tone is "warm", "cool" or "" and only
 * set on the temperature gap. A figure the server could not compute is left out.
 */
export function figures(answer, season) {
  const all = answer.figures;
  const reference = `${answer.reference_start.slice(0, 4)}-${answer.reference_end.slice(0, 4)}`;
  const words = texts.summary;
  const out = [];
  for (const key of PICKS[season] ?? PICKS.summer) {
    const figure = all[key];
    if (!figure || figure.value === null || figure.normal === null) continue;
    const { value, normal } = figure;
    if (key === "tasmax_mean" || key === "tas_mean") {
      const gap = Math.round((value - normal) * 10) / 10;
      out.push({
        key,
        value: `${SIGNED.format(gap)}\u00a0°C`,
        label: words[key](ONE.format(value)),
        normal: words.normal(reference, `${ONE.format(normal)}\u00a0°C`),
        tone: gap >= 0.5 ? "warm" : gap <= -0.5 ? "cool" : "",
      });
    } else if (key === "precipitation") {
      if (normal <= 0) continue;
      out.push({
        key,
        // The gap to the normal, as the temperature: -19 % rather than 81 %.
        value: `${PERCENT.format(Math.round((value / normal) * 100) - 100)}\u00a0%`,
        label: words.precipitation(String(Math.round(value))),
        normal: words.normal(reference, `${Math.round(normal)}\u00a0mm`),
        tone: "",
      });
    } else {
      const forty = key === "hot_35" ? all.hot_40?.value : null;
      out.push({
        key,
        value: count(value),
        label: words[key](value, forty ? count(forty) : null),
        normal: words.normal(reference, count(normal)),
        tone: "",
      });
    }
  }
  return out;
}

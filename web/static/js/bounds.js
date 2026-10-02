/**
 * What the form refuses before anything is fetched.
 *
 * The same three rules the API applies in `validation.py`, applied earlier. Two
 * copies of a rule is what CLAUDE.md rule 3 is about — but the rule it forbids
 * duplicating is one the server *computes a value from*, and these compute
 * nothing. They are a control, and a control may be exercised on both sides:
 * the API keeps enforcing them, because a limit only the browser applies is not
 * a limit, and this only spares the visitor a round trip.
 *
 * **The numbers themselves are not copied.** `maxDays`, and both ends of the
 * covered period, arrive from `/api/config`. That is the part which would
 * drift — a 90 written here would go on saying 90 the day the API said 120.
 *
 * The wording differs from the API's on purpose: these are typing mistakes
 * caught mid-form, not refusals of a search that was actually made.
 */

import { span } from "./calendar.js";
import { texts } from "./i18n.js";

/**
 * The reason to refuse, or null when there is none.
 *
 * `config` is what `/api/config` served: `coverage_start`, `coverage_end` and
 * `max_days`. Dates are ISO strings, which compare correctly as strings —
 * "1950-01-01" < "2050-12-31" — so nothing here parses a date, and nothing here
 * can slide a day by reading one in the wrong zone.
 */
export function refuse({ start, end }, config) {
  if (!start || !end) return texts.form.datesRequired;
  if (start > end) return texts.form.rangeInverted;
  if (start < config.coverage_start || end > config.coverage_end) {
    return texts.form.rangeOutsideCoverage(
      config.coverage_start.slice(0, 4),
      config.coverage_end.slice(0, 4),
    );
  }
  const days = span(start, end);
  if (days > config.max_days) return texts.form.rangeTooLong(config.max_days, days);
  if (!config.periods.some((p) => start >= p.start && end <= p.end)) {
    return texts.form.rangeUnavailable(periodsText(config));
  }
  return null;
}

/** The served periods as the visitor reads them: "1970 à 2025, 2027 à 2100". */
export function periodsText(config) {
  return config.periods
    .map((p) => texts.form.period(p.start.slice(0, 4), p.end.slice(0, 4)))
    .join(", ");
}

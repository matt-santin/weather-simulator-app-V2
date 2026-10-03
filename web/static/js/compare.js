/**
 * The seasonal normals, laid alongside the days on screen.
 *
 * A simulated 39 °C says nothing to a reader who does not know what a 14 July
 * used to be: the lesson is in the gap, not in the value. So the chart can carry
 * the 1991-2020 normals of the same dates, drawn in grey under the days. They
 * are computed by the server (`/api/normals`); this file only lines them up.
 *
 * No DOM, no state, no fetching: `node --test` is enough to check it.
 */

/**
 * The normals, one slot per day drawn, aligned on the date and never on the
 * index: a day the answer does not carry stays a hole (`null`) rather than
 * shoving every day after it out by one.
 */
export function alignByDate(days, normals) {
  const found = new Map(normals.map((normal) => [normal.date, normal]));
  return days.map((day) => found.get(day.date) ?? null);
}

/** The legend of the grey marks: "Normales 1991-2020". */
export function referenceYears(answer) {
  return `${answer.reference_start.slice(0, 4)}-${answer.reference_end.slice(0, 4)}`;
}

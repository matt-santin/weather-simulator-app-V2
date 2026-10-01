/**
 * The days on screen, as a file the visitor can keep.
 *
 * No DOM, no fetching, no state — the neighbour of `season.js` and `compare.js`,
 * and `node --test` is enough to check it. What writes the file to disk is
 * `results.js`; what it writes is here.
 *
 * **Nothing is computed.** Every column is a field the server served, written
 * out as it arrived. The running total is on the chart and not in the file: it
 * is the one aggregate `docs/application.md` admits, arbitrated for that panel,
 * and carrying it into a second surface would widen an exception nobody asked
 * to widen. A spreadsheet makes it from the precipitation column in one
 * formula.
 *
 * **`origine` and `source` are columns and not a header note.** A file outlives
 * the page it left: rows of temperatures with no origin would let simulated
 * days circulate as measurements, which is the one thing CLAUDE.md rule 1
 * exists to prevent. On a row apiece, the mark cannot be separated from the
 * number it qualifies — and it survives sorting, filtering and a copy into
 * another sheet.
 *
 * **Semicolons and decimal commas, which is a choice against the other one.**
 * A French spreadsheet opens this file by double-clicking it; `read_csv` needs
 * to be told `sep=";", decimal=","`. The reverse convention would swap who is
 * inconvenienced. The site is written in French for visitors rather than for
 * pipelines, so the visitor's double-click wins.
 */

import { texts } from "./i18n.js";
import { isMissing } from "./present.js";

/** What a French spreadsheet expects, and what a French decimal is. */
const SEPARATOR = ";";
const DECIMAL = ",";

/** RFC 4180's line ending, which is also the one every spreadsheet accepts. */
const EOL = "\r\n";

/**
 * The fields, in the order the file writes them.
 *
 * The date, then what produced it, then the readings — a reader meets the
 * qualification before the numbers it qualifies, in the file as on the page.
 */
const FIELDS = [
  "date",
  "origin",
  "source",
  "temperature_min",
  "temperature_max",
  "precipitation",
  "cloud_cover",
  "wind_speed_mean",
  "wet_bulb_mean",
  "humid_heat",
  "sky",
];

/** A number as French writes it, and an empty cell where there is no reading. */
function cell(value) {
  if (isMissing(value)) return "";
  if (typeof value !== "number") return String(value);
  return String(value).replace(".", DECIMAL);
}

/**
 * One field, quoted only where it has to be.
 *
 * Nothing this file writes carries a separator today — dates, identifiers,
 * numbers and five sky words. It is quoted all the same: the day a column is
 * added for something written by a human, an unquoted separator would not break
 * the file loudly, it would shift every column after it by one.
 */
function quote(value) {
  return /[";\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** One day, as its row: the words in French, the numbers as they were served. */
function row(day) {
  return FIELDS.map((field) => {
    if (field === "origin") return texts.export.origin[day.origin] ?? day.origin;
    if (field === "sky") return day.sky ? texts.sky[day.sky] : "";
    // Null and zero write the same empty cell here, where the contract keeps
    // them apart. A spreadsheet has no room for the difference between "nothing
    // to report" and "nothing was measured", and the wet-bulb column beside it
    // already says which of the two it is: a figure, or a blank.
    if (field === "humid_heat") return texts.export.humidHeat[day.humid_heat] ?? "";
    return cell(day[field]);
  });
}

/**
 * The whole file, header included.
 *
 * A trailing line ending, which is what a text file is: `wc -l` counts the last
 * row, and every reader ignores the empty line it makes.
 */
export function toCsv(days) {
  return [texts.export.columns(), ...days.map(row)]
    .map((cells) => cells.map(quote).join(SEPARATOR))
    .concat("")
    .join(EOL);
}

/**
 * What the file is called: the place and the range that produced it.
 *
 * **The name has to survive a download folder.** Two exports from the same
 * afternoon are two different searches, and `donnees.csv` twice would be
 * `donnees.csv` and `donnees (1).csv` — a pair nobody can tell apart a week
 * later. Place and dates make the name the search itself.
 *
 * Accents and spaces come out of it: the name travels to filesystems this page
 * knows nothing about, and a place name is whatever the visitor typed.
 */
export function fileName(place, start, end) {
  const slug = place
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return ["meteo", slug, start, end].filter(Boolean).join("-") + ".csv";
}

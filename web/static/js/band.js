/**
 * The strip of days, built as nodes. Nothing here fetches or holds state.
 *
 * Split off from results.js so that it can be checked: give it a series and it
 * hands back nodes, which a test can walk without a browser. What is left in
 * results.js is the page's wiring — the URL, the call, the waiting.
 *
 * **Three reading marks are added, and only three.** The month name where the
 * month turns, the seam where the observed stops, and whether the humid-heat
 * line is reserved at all. The server holds no version of
 * either — CLAUDE.md rule 3 turns on the double copy, and there is none here.
 * Everything else on a card arrived decided.
 *
 * What is deliberately *not* here: no average over the range, no count of rainy
 * days, no total, no extreme. An aggregate computed at display time falls under
 * the same validation as a rounding, and docs/application.md settles it — the
 * strip shows the days and nothing above them.
 */

import { el } from "./dom.js";
import { texts } from "./i18n.js";
import * as present from "./present.js";
import { at } from "./calendar.js";
import { seamIndex } from "./series.js";

/**
 * The days in order, laid on a calendar of seven columns, Monday first.
 *
 * **Each month opens on a line of its own**, its name and year across the seven
 * columns: the week is cut on the last day of the month before, and the new
 * month picks up under its weekday. The first month of the range opens the same
 * way. The line is hidden from screen readers, which hear the month on the
 * card that opens it (the card's month line, kept off screen).
 *
 * **Empty cells before the first day of each month**, so that each day falls
 * under its own weekday: a month starting on a Thursday opens with three. They
 * are hidden from screen readers too, which hear the weekday on every card and
 * have no column to lose. Nothing is padded after the last day of a month; the
 * row simply ends.
 *
 * **The seam rides on the first simulated card** rather than taking a cell of
 * its own: a cell would push every following day one column off its weekday.
 * It stays written, beside that card's date, since colour alone must never be
 * what carries it. *Where* it falls is series.js, shared with the chart under
 * the calendar, which has to mark the same crossing at the same day.
 */
export function strip(days, humidHeatPeak = 0) {
  const seam = seamIndex(days);
  const reservesHumidHeat = humidHeatPeak > 0;
  const nodes = [];
  let month = null;

  for (const [index, day] of days.entries()) {
    const turned = present.monthKey(day.date) !== month;
    month = present.monthKey(day.date);
    if (turned) {
      nodes.push(
        el("li", {
          className: "month-row",
          text: present.monthYear(day.date),
          attrs: { "aria-hidden": "true" },
        }),
      );
      for (let cell = 0; cell < weekdayIndex(day.date); cell += 1) {
        nodes.push(el("li", { className: "pad", attrs: { "aria-hidden": "true" } }));
      }
    }
    nodes.push(card(day, turned, reservesHumidHeat, index === seam));
  }
  return nodes;
}

/**
 * The legend of the calendar: one chip per band, coloured by the stylesheet
 * through `data-band` exactly like a card, with its bounds written in it. The
 * edges are the server's (`/api/config`), so the legend cannot drift from the
 * bands the cards carry.
 */
export function legend(edges) {
  const { legendTitle, legendBelow, legendBetween, legendAbove } = texts.results;
  const chips = [legendBelow(edges[0])];
  for (let index = 1; index < edges.length; index += 1) {
    chips.push(legendBetween(edges[index - 1], edges[index]));
  }
  chips.push(legendAbove(edges[edges.length - 1]));
  return el("div", { className: "band-legend" }, [
    el("span", { text: legendTitle, attrs: { id: "band-legend-title" } }),
    el(
      "ol",
      { attrs: { "aria-labelledby": "band-legend-title" } },
      chips.map((text, band) => el("li", { text, attrs: { "data-band": String(band) } })),
    ),
  ]);
}

/** 0 for a Monday, 6 for a Sunday. */
function weekdayIndex(iso) {
  return (new Date(at(iso)).getUTCDay() + 6) % 7;
}

/**
 * One day, one card, with a hierarchy: the sky and the two temperatures lead,
 * the rain and the wind follow at equal weight to each other.
 *
 * Both of those are display decisions the project owner took on seeing the
 * first strip. Four measures at one rank left nothing for the eye to land on —
 * the card read as a table. And `wind_speed_mean` came off the card entirely:
 * five numbers were more than one can carry at a glance. It still travels in
 * the JSON contract, where keeping it costs nothing.
 *
 * `source` rides along as a title attribute: it is what tells one seam from the
 * other when something looks wrong, and it has no business on screen otherwise.
 */
export function card(day, namesMonth, reservesHumidHeat = false, opensSimulation = false) {
  const { emoji, label } = present.sky(day.sky);
  const { celsius, millimetres, kilometresPerHour, percent } = texts.units;
  const className = `card card--${day.origin}${opensSimulation ? " card--seam" : ""}`;

  // The band of the maximum tints the whole card. It arrives decided by the
  // server and is written as an attribute, never as a colour: the hues live in
  // the stylesheet, exactly as the pictogram lives here rather than in the JSON.
  // A day with no maximum carries no attribute and keeps the plain paper: a gap
  // is not a shade of cold.
  const band = day.temperature_max_band;
  return el("li", {
    className,
    attrs: {
      title: day.source,
      // The day, for what a card leads to (the map of that day, dayzoom.js).
      "data-date": day.date,
      "data-band": band === null || band === undefined ? undefined : String(band),
    },
  }, [
    // The tinted band. The month line is rendered on every card, empty where the
    // month has not turned, so the cards keep one height and the dates line up
    // across the strip.
    //
    // **Written out on the turn alone, and that only works because the day
    // carries the month in figures.** Naming it on every card was tried first
    // and it cost the turn its salience: "AOÛT" among a run of "JUILLET" no
    // longer marks anything. Two digits on the date line — "lundi 01/08" — say
    // the month wherever the reader has scrolled to, and leave the name to the
    // one card that has news.
    el("div", { className: "card-head" }, [
      // **Two dates, one of them read.** On the calendar the column says the
      // weekday and the line above the month says the month, so the card shows
      // the day of the month alone; the full "lundi 01/08" and the month line
      // stay for the screen reader, and the list shown on a narrow window prints
      // the full date instead.
      el("p", {
        className: "card-month",
        text: namesMonth ? present.monthLabel(day.date) : "",
      }),
      el("p", { className: "card-day" }, [
        el("span", { className: "card-date-long", text: present.dayLabel(day.date) }),
        el("span", {
          className: "card-date-short",
          text: present.dayOfMonth(day.date),
          attrs: { "aria-hidden": "true" },
        }),
        ...(opensSimulation ? [el("span", { className: "card-seam", text: texts.results.seamCard })] : []),
      ]),
    ]),
    el("div", { className: "card-body" }, [
      // The emoji is hidden from screen readers and the written class carries it
      // instead. docs/application.md requires both, one for each way of reading.
      el("p", { className: "card-emoji", text: emoji, attrs: { "aria-hidden": "true" } }),
      // Straight under the pictogram, large, and unlabelled: two numbers beside
      // a degree sign on a weather card need no word to say what they are.
      // Which is the maximum *does* need saying — that is carried by size and
      // by position on screen, and neither is information, so each is named for
      // anyone not reading them.
      //
      // **Maximum first, and larger.** The earlier card ran "min · max", in the
      // order projet.md and the README write the pair; the results mock-up led
      // with the maximum, the figure a summer read is looking for. Stacked while
      // each had a tinted box, side by side since the tint moved to the whole
      // card (2026-10-16), the minimum smaller and softened. The reading order
      // follows the eye, and band.test.js pins it.
      el("p", { className: "card-temperatures" }, [
        el("span", { className: "sr-only", text: texts.measure.high }),
        degrees(day.temperature_max, "high", celsius),
        el("span", { className: "sr-only", text: texts.measure.low }),
        degrees(day.temperature_min, "low", celsius),
      ]),
      el("p", { className: "card-sky", text: label }),
      el("dl", { className: "card-measures" }, [
        ...measure(texts.measure.precipitation, day.precipitation, present.precipitation, millimetres),
        ...measure(texts.measure.humidity, day.relative_humidity_mean, present.humidity, percent),
        // The daily mean wind: CORDEX serves no daily maximum.
        ...measure(texts.measure.windMean, day.wind_speed_mean, present.wind, kilometresPerHour),
      ]),
      // Under the wind, and reserved on every card of the strip or on none.
      ...(reservesHumidHeat ? [humidHeat(day)] : []),
      detail(day),
    ]),
  ]);
}

/**
 * The table the enlarged card shows: every reading on a line of its own, the
 * word on the left, the figure and its unit on the right, all at one size.
 *
 * Off screen on the card itself, which shows its maximum alone, and hidden
 * from screen readers, which hear the same readings from the card above it
 * (dayzoom.js draws the enlarged copy, the stylesheet shows this table there).
 */
function detail(day) {
  const { celsius, millimetres, kilometresPerHour, percent } = texts.units;
  const rows = [
    [texts.detail.high, day.temperature_max, present.temperature, celsius],
    [texts.detail.low, day.temperature_min, present.temperature, celsius],
    [texts.detail.precipitation, day.precipitation, present.precipitation, millimetres],
    [texts.detail.humidity, day.relative_humidity_mean, present.humidity, percent],
    [texts.detail.wind, day.wind_speed_mean, present.wind, kilometresPerHour],
  ];
  return el(
    "dl",
    { className: "card-detail", attrs: { "aria-hidden": "true" } },
    rows.flatMap(([label, raw, format, unit]) => [
      el("dt", { text: label }),
      el("dd", {}, [
        el("span", { className: "value", text: format(raw) }),
        el("span", { className: "unit", text: unit }),
      ]),
    ]),
  );
}

/**
 * The humid-heat line: a word where there is one, an empty line where there is
 * not, and never a number.
 *
 * **Empty rather than absent.** The cards are stretched to the tallest, so a
 * line appearing on one day alone would grow the other eighty-nine and move the
 * strip under the reader. The month line above already answers that the same
 * way. What keeps this from costing anything is one rank up: `strip` reserves
 * nothing at all on a range that carries no level, which is every range in
 * France.
 *
 * **The word first, then the figure under it.** A wet bulb has no scale a
 * reader can call on: 31 °C is lethal and reads as mild, and the card already
 * carries two temperatures in large type, so a third bare number would read as
 * a third air temperature. The order is what answers that. The word arrives
 * first and names what follows, and the figure is set as a measure rather than
 * as a headline — the type of "0,4 mm" and not that of the maximum — so the eye
 * takes it for what it is. The project owner asked for the number on 2026-09-07,
 * against the earlier arbitration; what is kept of that arbitration is that the
 * number never stands alone.
 *
 * **The level arrives decided.** `humid_heat` is the server's answer, not a
 * comparison made here: a threshold is a rule a displayed quantity turns on, and
 * CLAUDE.md rule 3 keeps those on one side. This file knows there are levels,
 * never where they start.
 */
function humidHeat(day) {
  const level = day.humid_heat;
  if (!level) return el("p", { className: "card-humid" });

  const shown = present.temperature(day.wet_bulb_mean);
  const reading = texts.humidHeat.reading(shown);
  return el(
    "p",
    { className: "card-humid", attrs: { "data-humid": String(level), title: reading } },
    [
      el("span", { text: `${texts.humidHeat.mark} `, attrs: { "aria-hidden": "true" } }),
      el("span", { text: texts.humidHeat.level[level] }),
      // The name of the quantity, read aloud and not shown — the division
      // `measure` already makes between a label and the bare number a card
      // prints. Without it the figure arrives with no word at all for anyone
      // who cannot see the line it sits under.
      el("span", { className: "sr-only", text: texts.humidHeat.valueLabel }),
      el("span", { className: "card-humid-value" }, [
        el("span", { className: "value", text: shown }),
        el("span", { className: "unit", text: texts.units.celsius }),
      ]),
    ],
  );
}

/** One number, and what to say instead of it when there is none. */
function value(shown, raw, className) {
  return el("span", {
    className,
    text: shown,
    attrs: {
      "aria-label": present.isMissing(raw) ? texts.measure.missingLabel : undefined,
    },
  });
}

/**
 * One temperature, degree sign included. The unit rides on each of the two,
 * the maximum and the minimum being set at two sizes.
 */
function degrees(raw, className, unit) {
  return el("span", { className: `card-degrees ${className}` }, [
    value(present.temperature(raw), raw, "value"),
    el("span", { className: "unit", text: unit }),
  ]);
}

/**
 * A measure: the word, then the number and its unit.
 *
 * **The word is carried but not shown.** The mock-up puts bare figures on the
 * card — "3,2 mm", "5 km/h" — and the units make them legible at a glance. A
 * screen reader gets no units to lean on, so the `dt` stays in the document and
 * goes off-screen instead of away: that is what keeps "Vent maximal" attached
 * to a number docs/application.md forbids reading as an average.
 */
function measure(label, raw, format, unit) {
  return [
    el("dt", { className: "sr-only", text: label }),
    el("dd", { className: "card-measure" }, [
      value(format(raw), raw, "value"),
      el("span", { className: "unit", text: unit }),
    ]),
  ];
}

/**
 * What corrected the simulated days, as label/value pairs.
 *
 * Empty when the grid is null, which is the honest answer for a range lying
 * wholly in the past: nothing was corrected, so there is no table to describe.
 */
export function sources(grid) {
  if (!grid) return [];
  const rows = [
    [texts.provenance.model, grid.model],
    [texts.provenance.reference, grid.reference],
    [
      texts.provenance.calibration,
      texts.provenance.span(
        present.fullDate(grid.calibration_start),
        present.fullDate(grid.calibration_end),
      ),
    ],
    [
      texts.provenance.projection,
      texts.provenance.span(
        present.fullDate(grid.projection_start),
        present.fullDate(grid.projection_end),
      ),
    ],
    [texts.provenance.step, step(grid)],
    [texts.provenance.generated, present.fullDate(grid.generated)],
  ];
  return rows.flatMap(([label, text]) => [el("dt", { text: label }), el("dd", { text })]);
}

/** "0,25°", or "0,1° (températures), 0,25°" where the temperatures are finer. */
function step(grid) {
  const degrees = (value) => texts.provenance.degrees(String(value).replace(".", ","));
  if (grid.temperature_step == null) return degrees(grid.step);
  return texts.provenance.steps(degrees(grid.temperature_step), degrees(grid.step));
}

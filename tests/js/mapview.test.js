/**
 * The arithmetic of the map page: bands on the site's edges, a projection that
 * is its own inverse, the grid image the cells are drawn into, and the summary
 * of a day.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  COLORS,
  FILL,
  MAX_ZOOM,
  WHOLE,
  band,
  grid,
  pan,
  projection,
  summary,
  unzoom,
  VARIABLES,
  zoomAt,
} from "../../web/static/js/mapview.js";

const EDGES = [5, 10, 15, 20, 25, 30, 35, 40];

describe("the bands", () => {
  it("follow the site's edges, an edge belonging to the band above", () => {
    assert.equal(band(-3, EDGES), 0);
    assert.equal(band(5, EDGES), 1);
    assert.equal(band(39.9, EDGES), 7);
    assert.equal(band(40, EDGES), 8);
    assert.equal(COLORS.length, EDGES.length + 1);
  });
});

describe("the projection", () => {
  it("is its own inverse", () => {
    const view = projection({ west: -25, east: 45, south: 34, north: 72 }, 800);
    const [x, y] = view.project(2.35, 48.85);
    const [lon, lat] = view.unproject(x, y);
    assert.ok(Math.abs(lon - 2.35) < 1e-9 && Math.abs(lat - 48.85) < 1e-9);
    assert.deepEqual(view.project(-25, 72), [0, 0]);
  });
});

describe("the grid image", () => {
  const cells = { north: 73, west: -45, step: 0.25, rows: [4, 4, 6], cols: [80, 82, 81] };

  it("starts at the first used row and column", () => {
    const g = grid(cells);
    assert.equal(g.rows, 3);
    assert.equal(g.cols, 3);
    assert.deepEqual(g.at, [0, 2, 7]);
    assert.equal(g.index.get(7), 2);
  });

  it("knows where each cell is", () => {
    const g = grid(cells);
    assert.equal(g.latitude(0), 72);
    assert.equal(g.longitude(1), -24.5);
    // The image's edges are half a step outside the outer cell centres.
    assert.equal(g.north, 72.125);
    assert.equal(g.west, -25.125);
  });
});

describe("the summary of a day", () => {
  it("finds the hottest cell, the median and the bands, skipping missing values", () => {
    const s = summary(Int16Array.from([123, 405, FILL, 250]), EDGES);
    assert.equal(s.hottest, 40.5);
    assert.equal(s.at, 1);
    assert.equal(s.median, 25);
    assert.equal(s.cells, 3);
    assert.equal(s.counts[2], 1); // 12,3
    assert.equal(s.counts[5], 1); // 25,0
    assert.equal(s.counts[8], 1); // 40,5
  });
});

describe("the zoom", () => {
  it("keeps the point under the pointer where it is", () => {
    const z = zoomAt(WHOLE, 2, 300, 200, 800, 600);
    assert.equal(z.scale, 2);
    const [px, py] = unzoom(z, 300, 200, 800, 600);
    assert.ok(Math.abs(px - 300) < 1e-9 && Math.abs(py - 200) < 1e-9);
  });

  it("stays between the whole map and the maximum", () => {
    assert.equal(zoomAt(WHOLE, 0.5, 0, 0, 800, 600).scale, 1);
    assert.equal(zoomAt(WHOLE, 100, 0, 0, 800, 600).scale, MAX_ZOOM);
  });

  it("never pans the map off its frame", () => {
    const z = zoomAt(WHOLE, 2, 400, 300, 800, 600);
    assert.deepEqual(pan(z, 10000, 10000, 800, 600), { scale: 2, x: 0, y: 0 });
    assert.deepEqual(pan(z, -10000, -10000, 800, 600), { scale: 2, x: -1, y: -1 });
    assert.deepEqual(pan(WHOLE, 50, 50, 800, 600), WHOLE);
  });
});

describe("the scales of each variable", () => {
  it("give one colour per band", () => {
    for (const [name, spec] of Object.entries(VARIABLES)) {
      if (spec.edges) assert.equal(spec.colors.length, spec.edges.length + 1, name);
    }
  });

  it("run the minima from -20 to 30 °C, turning at frost and at warm nights", () => {
    const { edges } = VARIABLES.tasmin;
    assert.equal(edges[0], -20);
    assert.equal(edges.at(-1), 30);
    assert.ok(edges.includes(0) && edges.includes(20));
    assert.equal(band(-0.1, edges), 4);
    assert.equal(band(0, edges), 5);
    assert.equal(VARIABLES.tasmin.first, "min");
  });
});

describe("the coldest cell", () => {
  it("is found beside the hottest one", () => {
    const s = summary(Int16Array.from([-153, 405, FILL, 12]), EDGES);
    assert.equal(s.coldest, -15.3);
    assert.equal(s.coldAt, 0);
  });
});

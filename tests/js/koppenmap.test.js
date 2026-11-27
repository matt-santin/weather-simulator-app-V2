/** The arithmetic of /climats (koppenmap.js): cells, classes, legend, paint. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { cellOf, classAt, COLORS, paint, present, rgb } from "../../web/static/js/koppenmap.js";

const meta = { north: 50, west: 0, step: 0.1, rows: 3, cols: 4, codes: ["", "Cfa", "Cfb", "Dfb"] };
// Row 0 to the north.
const grid = Uint8Array.from([2, 2, 1, 0, 2, 1, 1, 0, 3, 3, 0, 0]);

describe("the cells of the grid", () => {
  it("finds the cell under a point, centres on the grid", () => {
    assert.equal(cellOf(meta, 0, 50), 0);
    assert.equal(cellOf(meta, 0.3, 49.9), 7);
    assert.equal(cellOf(meta, 0.04, 49.96), 0);
    assert.equal(cellOf(meta, -1, 50), -1);
    assert.equal(cellOf(meta, 0, 52), -1);
  });

  it("reads the class code, nothing over the sea", () => {
    assert.equal(classAt(meta, grid, 0.1, 50), "Cfb");
    assert.equal(classAt(meta, grid, 0.2, 49.9), "Cfa");
    assert.equal(classAt(meta, grid, 0.3, 50), "");
    assert.equal(classAt(meta, grid, 9, 9), "");
  });
});

describe("the legend and the colours", () => {
  it("lists the classes of every grid once, in the order of the legend", () => {
    assert.deepEqual(present(meta, grid), ["Cfa", "Cfb", "Dfb"]);
    assert.deepEqual(present(meta, Uint8Array.from([0, 2, 2])), ["Cfb"]);
  });

  it("has a colour for each of the thirty classes, as Beck et al. 2023", () => {
    assert.equal(Object.keys(COLORS).length, 30);
    assert.deepEqual(rgb(COLORS.Cfb), [100, 255, 80]);
  });

  it("paints each pixel with the class under its centre, the sea transparent", () => {
    // One pixel per cell: x is the column, y the row.
    const unproject = (x, y) => [meta.west + (x - 0.5) * meta.step, meta.north - (y - 0.5) * meta.step];
    const pixels = paint(meta, grid, 4, 3, unproject);
    assert.deepEqual([...pixels.slice(0, 4)], [...rgb(COLORS.Cfb), 255]);
    assert.deepEqual([...pixels.slice(8, 12)], [...rgb(COLORS.Cfa), 255]);
    assert.equal(pixels[3 * 4 + 3], 0);
  });
});

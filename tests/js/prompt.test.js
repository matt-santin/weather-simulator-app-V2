/**
 * The rotating question: what it builds, and what it exposes at a given moment.
 *
 * Not the timer. `rotate` wires intervals, pointer events and a media query,
 * none of which is arithmetic — so the module keeps the decidable part apart and
 * this file takes that on: one node per question, one of them current, and the
 * heading reading as exactly one sentence rather than ten in a row.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { byClass, install, reads } from "./dom-stub.js";

install();

const { build, next, reveal, rotate } = await import("../../web/static/js/prompt.js");
const { texts } = await import("../../web/static/js/i18n.js");

const THREE = ["Une ?", "Deux ?", "Trois ?"];

describe("the order", () => {
  it("comes back to the first after the last", () => {
    assert.equal(next(0, 3), 1);
    assert.equal(next(1, 3), 2);
    assert.equal(next(2, 3), 0);
  });

  it("stays put on a single question", () => {
    assert.equal(next(0, 1), 0);
  });

  it("does not divide by an empty list", () => {
    // A dictionary that has lost its questions must leave the banner blank, not
    // take the page down.
    assert.equal(next(0, 0), 0);
  });
});

describe("the stack", () => {
  it("gives every question a node of its own", () => {
    const nodes = build(THREE);
    assert.equal(nodes.length, 3);
    assert.deepEqual(
      nodes.map((node) => node.textContent),
      THREE,
    );
    assert.ok(nodes.every((node) => node.className === "prompt-item"));
  });

  it("builds nothing from nothing", () => {
    assert.deepEqual(build([]), []);
  });
});

describe("what is exposed", () => {
  it("marks one node current and no other", () => {
    const nodes = build(THREE);
    reveal(nodes, 1);
    assert.deepEqual(
      nodes.map((node) => node.classList.contains("is-current")),
      [false, true, false],
    );
  });

  it("hides the rest from the accessibility tree", () => {
    // The whole reason the heading may change at all: read aloud it must be one
    // question, not the list.
    const nodes = build(THREE);
    reveal(nodes, 2);
    const heading = { className: "", textContent: "", attrs: {}, children: nodes };
    assert.equal(reads(heading), "Trois ?");
  });

  it("takes the hiding back when a node becomes current again", () => {
    const nodes = build(THREE);
    reveal(nodes, 0);
    reveal(nodes, 1);
    reveal(nodes, 0);
    assert.equal(nodes[0].attrs["aria-hidden"], undefined);
    assert.equal(nodes[1].attrs["aria-hidden"], "true");
  });
});

describe("the questions themselves", () => {
  it("are there, and each one asks something", () => {
    assert.ok(texts.home.questions.length >= 1);
    assert.ok(texts.home.questions.every((question) => question.trim().endsWith("?")));
  });

  it("leave the promise to the subtitle", () => {
    // The heading asks; the line under it answers what the site does. What the
    // answer must keep is the verb: rule 1 names "simulation" among the terms
    // it allows, and it is the verb that makes the sentence an offer to try
    // rather than a claim about a day. present.test.js covers the words the
    // rule forbids; this covers the one it needs.
    assert.match(texts.home.promise, /^Simulez /);
  });
});

/**
 * The timer, which this file used to leave alone.
 *
 * It is checkable after all, with a fake clock and a stub that carries events —
 * and it was worth checking, because the rule it enforces is an accessibility
 * one. WCAG 2.2.2: anything that moves on its own for more than five seconds
 * owes the reader a way to stop it. What follows is that the way to stop it has
 * to keep working, including when a second reason to stop arrives and leaves
 * while the first is still there.
 */
describe("the rotation, and what stops it", () => {
  const setUp = (t) => {
    // setInterval covers clearInterval; naming it separately is refused.
    t.mock.timers.enable({ apis: ["setInterval"] });
    const host = document.createElement("div");
    const stop = rotate(host, ["une", "deux", "trois"], { interval: 1000 });
    return { host, stop, shown: () => byClass(host, "is-current")[0].textContent };
  };

  it("turns over on its own", (t) => {
    const { shown } = setUp(t);
    assert.equal(shown(), "une");
    t.mock.timers.tick(1000);
    assert.equal(shown(), "deux");
    t.mock.timers.tick(1000);
    assert.equal(shown(), "trois");
  });

  it("holds still under the pointer", (t) => {
    const { host, shown } = setUp(t);
    host.dispatchEvent(new Event("mouseenter"));
    t.mock.timers.tick(5000);
    assert.equal(shown(), "une");

    host.dispatchEvent(new Event("mouseleave"));
    t.mock.timers.tick(1000);
    assert.equal(shown(), "deux");
  });

  it("holds still while the tab is in the background", (t) => {
    const { shown } = setUp(t);
    document.hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    t.mock.timers.tick(5000);
    assert.equal(shown(), "une");

    document.hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    t.mock.timers.tick(1000);
    assert.equal(shown(), "deux");
  });

  it("stays still when a tab returns under a pointer that stopped it", (t) => {
    // The bug this replaced: two reasons to stop, one of them lifted, and the
    // rotation started again under a pointer that had asked for stillness.
    const { host, shown } = setUp(t);
    host.dispatchEvent(new Event("mouseenter"));
    document.hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    document.hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));

    t.mock.timers.tick(5000);
    assert.equal(shown(), "une", "la rotation a repris sous le pointeur");

    // And it is not stuck either: lifting the reason that remains frees it.
    host.dispatchEvent(new Event("mouseleave"));
    t.mock.timers.tick(1000);
    assert.equal(shown(), "deux");
  });

  it("stays stopped once the caller has stopped it", (t) => {
    const { host, stop, shown } = setUp(t);
    stop();
    // A pointer leaving a banner it never entered must not undo that.
    host.dispatchEvent(new Event("mouseleave"));
    t.mock.timers.tick(5000);
    assert.equal(shown(), "une");
  });
});

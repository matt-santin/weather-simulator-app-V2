/**
 * The slots the pages mark, against the dictionary that fills them.
 *
 * `applyTexts` fills `data-text="form.place"` from `texts.form.place`, and a
 * key that resolves to nothing is written as the empty string — `lookup(...) ??
 * ""`. That fallback is right at runtime, a missing sentence being no reason to
 * take a page down, and it is exactly what makes the mistake invisible: a
 * mistyped key produces a label that is simply not there, on a page nobody
 * looks at every day. Renaming a key in i18n.js and missing one of its two
 * pages costs a heading, silently.
 *
 * So the join is checked here instead. The pages are read as files and the keys
 * resolved through `lookup` itself — the real one, imported, not a second
 * walker written for the test. A copy of that reduce would be the very
 * duplication CLAUDE.md rule 3 is about, and it would go on agreeing with
 * itself while disagreeing with the page.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { lookup } from "../../web/static/js/dom.js";

const PAGES = ["home.html", "results.html"];

/** Every slot a page marks: `data-text`, and `data-attr-*` for an attribute. */
const SLOT = /data-(?:text|attr-[a-z-]+)="([^"]+)"/g;

function slotsOf(page) {
  const html = readFileSync(new URL(`../../web/pages/${page}`, import.meta.url), "utf8");
  return [...html.matchAll(SLOT)].map((match) => match[1]);
}

describe("every sentence a page asks for", () => {
  for (const page of PAGES) {
    const slots = slotsOf(page);

    it(`${page} marks slots at all`, () => {
      // Guards the guard: a regex that silently matched nothing would let every
      // assertion below pass on an empty list.
      assert.ok(slots.length > 0, `aucun data-text trouvé dans ${page}`);
    });

    it(`${page} names only keys the dictionary has`, () => {
      const dangling = slots.filter((key) => lookup(key) === undefined);
      assert.deepEqual(dangling, [], `clés absentes de i18n.js : ${dangling.join(", ")}`);
    });

    it(`${page} names a sentence, never a branch of the dictionary`, () => {
      // `data-text="form"` resolves — to an object, which a page writes out as
      // "[object Object]". A function does no better: `form.candidates` counts
      // its argument, and pointed at from the markup it would print its own
      // source. Both are keys that exist and say nothing.
      const wrong = slots.filter((key) => typeof lookup(key) !== "string");
      assert.deepEqual(wrong, [], `clés qui ne sont pas une phrase : ${wrong.join(", ")}`);
    });
  }
});

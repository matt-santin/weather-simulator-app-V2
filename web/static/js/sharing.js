/**
 * The window of the "Partager" pill of the results page (18/11/2026): the
 * picture of the season (sharecard.js) in a square or a story, and three ways
 * out: the share sheet of the device (the picture and the link), the link
 * copied, the picture downloaded.
 *
 * A native <dialog>, opened modal: the focus is held in it, Escape closes it,
 * and the focus returns to the pill. The picture is drawn when the window
 * opens, once per format, after the fonts it uses are loaded: a canvas does not
 * wait for a web font, and draws in the fallback one if it is not there.
 */

import { draw, FONTS, FORMATS, fileName, message } from "./sharecard.js";
import { texts } from "./i18n.js";

/**
 * Wire ``opener`` to the dialog ``dialog`` (results.html, #share); ``gather``
 * returns the card (sharecard.js, `content`) at the time of the click, so that
 * the summary, which may arrive after the days, is in it when it is there.
 */
export function wireShare(opener, dialog, gather) {
  const preview = dialog.querySelector("#share-preview");
  const status = dialog.querySelector("#share-status");
  const native = dialog.querySelector("#share-native");
  const formats = [...dialog.querySelectorAll("[data-format]")];
  const words = texts.share;
  let card = null;
  let format = "square";
  let pictures = new Map(); // format -> Promise<Blob>
  let drawn = new Map(); // format -> Blob, once drawn
  let shownUrl = null;

  native.hidden = typeof navigator.share !== "function";

  const picture = (wanted) => {
    if (!pictures.has(wanted)) {
      const kept = pictures;
      kept.set(wanted, render(card, wanted).then((blob) => {
        if (kept === pictures) drawn.set(wanted, blob);
        return blob;
      }));
    }
    return pictures.get(wanted);
  };

  const showPreview = async () => {
    const blob = await picture(format);
    if (shownUrl) URL.revokeObjectURL(shownUrl);
    shownUrl = URL.createObjectURL(blob);
    preview.src = shownUrl;
    preview.dataset.format = format;
  };

  const say = (text) => {
    status.textContent = text;
  };

  opener.addEventListener("click", async () => {
    card = gather();
    pictures = new Map();
    drawn = new Map();
    preview.alt = message(card);
    say("");
    dialog.showModal();
    try {
      await showPreview();
    } catch {
      say(words.failed);
    }
  });

  for (const button of formats) {
    button.addEventListener("click", async () => {
      format = button.dataset.format;
      for (const other of formats) other.setAttribute("aria-pressed", String(other === button));
      try {
        await showPreview();
      } catch {
        say(words.failed);
      }
    });
  }

  dialog.querySelector("#share-close").addEventListener("click", () => dialog.close());
  // A click on the backdrop (the dialog itself, outside its content) closes it.
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  dialog.querySelector("#share-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      say(words.copied);
    } catch {
      say(words.copyFailed(window.location.href));
    }
  });

  dialog.querySelector("#share-download").addEventListener("click", async () => {
    try {
      const blob = await picture(format);
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = fileName(card.title, format);
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
      say(words.downloaded);
    } catch {
      say(words.failed);
    }
  });

  native.addEventListener("click", async () => {
    const url = window.location.href;
    const text = message(card);
    try {
      // The picture drawn when the window opened, taken without waiting: Safari
      // refuses a share sheet asked for after a pause in the click.
      const blob = drawn.get(format) ?? (await picture(format));
      const file = new File([blob], fileName(card.title, format), { type: "image/png" });
      // Some share targets drop `url` when a file travels with it: the link is
      // in the text as well.
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: card.title, text: `${text} ${url}` });
      } else {
        await navigator.share({ title: card.title, text, url });
      }
      say("");
    } catch (error) {
      // The visitor closing the sheet is not a failure.
      if (error?.name !== "AbortError") say(words.failed);
    }
  });
}

/** The picture of ``card`` in ``format``, as a PNG blob. */
async function render(card, format) {
  if (document.fonts?.load) await Promise.all(FONTS.map((font) => document.fonts.load(font)));
  const { width, height } = FORMATS[format];
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  draw(canvas.getContext("2d"), card, format);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("no picture"))), "image/png"));
}

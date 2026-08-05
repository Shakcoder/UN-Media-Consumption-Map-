/* Shared date-range control — used by the Map's UN News analytics panel,
 * Topic Explorer, Market Finder and the AI Analyst page (Task 6, 2026-08-04).
 *
 * Deliberately dependency-free and dumb: it renders segmented buttons and
 * reports the selected key. Each page decides what a range MEANS for its own
 * data — GA windows are pre-published aggregates (so every number still
 * matches the analytics source for that exact window), the Topic Explorer
 * slices its own 120-day series client-side, and survey-based figures are
 * never re-scoped by date (they are annual editions; pages say so instead of
 * faking precision).
 */
(function () {
  "use strict";

  function css(on) {
    return "font:inherit;font-size:11.5px;line-height:1;padding:5px 11px;border-radius:999px;cursor:pointer;" +
      "transition:background .15s;border:1px solid " +
      (on
        ? "var(--un-blue,#009edb);background:var(--un-blue,#009edb);color:#fff;"
        : "var(--line,#d8dee5);background:transparent;color:inherit;");
  }

  /**
   * Mount a segmented date-range control.
   * @param {Element} container - element to append into
   * @param {Object} opts
   *   options: [{key, label, title?}] — the ranges offered
   *   active: key selected initially
   *   onChange: function(key) — called on every change
   *   ariaLabel: accessible name for the group
   *   note: optional fine-print string rendered after the buttons
   * @returns {{active: string, set: function(string)}}
   */
  window.AtlasDateRange = function (container, opts) {
    var wrap = document.createElement("div");
    wrap.setAttribute("role", "group");
    wrap.setAttribute("aria-label", opts.ariaLabel || "Date range");
    wrap.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0;";
    var active = opts.active;
    var btns = {};

    (opts.options || []).forEach(function (o) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = o.label;
      if (o.title) b.title = o.title;
      b.setAttribute("aria-pressed", String(o.key === active));
      b.style.cssText = css(o.key === active);
      b.addEventListener("click", function () {
        if (o.key === active) return;
        active = o.key;
        Object.keys(btns).forEach(function (k) {
          btns[k].setAttribute("aria-pressed", String(k === active));
          btns[k].style.cssText = css(k === active);
        });
        opts.onChange(o.key);
      });
      btns[o.key] = b;
      wrap.appendChild(b);
    });

    if (opts.note) {
      var n = document.createElement("span");
      n.textContent = opts.note;
      n.style.cssText = "font-size:10px;color:var(--muted-2,#8a94a6);";
      wrap.appendChild(n);
    }

    container.appendChild(wrap);
    return {
      get active() { return active; },
      set: function (k) { if (btns[k] && k !== active) btns[k].click(); }
    };
  };
})();

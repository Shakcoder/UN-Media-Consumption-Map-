/* Shared CSV export helper (2026-08-18). Used by the Topic Explorer and the
 * Map's country profile. The Market Finder and the AI Analyst's question log
 * grew their own inline exports earlier under the same rules; this file
 * centralises those rules for every export added since, so a spreadsheet
 * downloaded anywhere on the Atlas behaves the same way in Excel.
 *
 * The rules (matching ask.html's question-log export):
 * - a UTF-8 byte-order mark, so Excel opens accented and non-Latin text
 *   correctly instead of guessing the encoding;
 * - CRLF row endings (RFC 4180 — what spreadsheet apps expect);
 * - a cell is quoted whenever it contains a comma, quote or line break;
 * - text cells that start with =, +, -, @, tab or carriage return are
 *   prefixed with a space so a spreadsheet app treats them as text, never
 *   as a formula (the same guard set ask.html and finder.html use; Excel
 *   treats a leading '-' as a formula too). Topic labels come from public
 *   wikis, so "looks like a formula" is not hypothetical. Numbers are
 *   passed through untouched, so negative figures stay real numbers;
 * - the download URL is revoked after a grace period, never in the same
 *   tick (revoking immediately can cancel the download in some browsers).
 */
(function () {
  "use strict";

  function cell(v) {
    if (v == null) return "";
    if (typeof v === "number") return String(v);
    let s = String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = " " + s;
    if (/[",\r\n]/.test(s)) s = '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  /**
   * Build a CSV from rows (arrays of cells) and hand it to the browser as a
   * file download.
   * @param {string} filename - e.g. "atlas-topic-movers-2026-08-16.csv"
   * @param {Array<Array>} rows - one array per row; cells may be strings,
   *   numbers or null/undefined (rendered empty)
   */
  function download(filename, rows) {
    const csv = "\uFEFF" + rows.map((r) => r.map(cell).join(",")).join("\r\n");
    const a = document.createElement("a");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }

  window.AtlasCSV = { cell: cell, download: download };
})();

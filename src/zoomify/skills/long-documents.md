---
name: long-documents
title: Long screenshots, scans & multi-page PDFs
description: Working through tall or wide captures, scanned pages, tables, forms, and PDFs page by page without skipping anything.
---

# Long screenshots, scans & multi-page PDFs

Read `zoom-basics` first.

## Tall or wide images

A long scrolling capture is shrunk heavily in the overview. Treat it as a strip:

1. From the root view, note the number of rows (or columns for a wide image).
2. Zoom into **bands** — a few full-width rows at a time, such as `1-3-A-H`,
   then `restore` and take `4-6-A-H`, and so on.
3. Overlap bands by one row when content may straddle a boundary.
4. Keep a running note of which bands you have covered.

## PDFs

- `open_image` renders one page at a time; pass `page` (1-based). The result
  reports how many pages the document has.
- Each page is its own session. Finish a page before opening the next, and say
  which page every value came from.
- For a document question ("find the certificate number"), check the first page
  and any page whose overview looks like a form or table before reading
  everything.

## Tables

- Read the header row first and keep the column order in your notes.
- Go through the body in bands of rows. For wide tables, split by column groups
  and re-read the first column each time so rows stay aligned.
- Empty cells are data: report them as empty, do not shift values across.
- Totals rows are a free check — if your extracted numbers do not add up to the
  printed total, re-zoom the rows that look doubtful.

## Forms and scans

- Printed field labels and handwritten or stamped entries need different zoom
  levels; handwriting usually needs factor 4 or more.
- Checkboxes: zoom until the mark itself is unambiguous.
- Skewed or low-contrast scans: prefer smaller selections at higher factors.
- Dates, IDs, and amounts are where a single wrong character matters most —
  read them twice at different zoom levels if they are faint.

## Screenshots

- Status bars, toolbars, and badges are tiny: zoom into the edges of the window
  deliberately, they are easy to ignore.
- Report text exactly as shown, including truncation (`…`).

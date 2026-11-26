---
name: long-documents
title: Long screenshots, scans & multi-page PDFs
description: Working through tall or wide captures, scanned pages, tables, forms, and multi-page PDFs (send once, pick a page by number, zoom) without skipping anything.
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

A PDF is sent to the server **once** and then addressed by **page number**. The
server keeps the file and renders only the page you ask for.

1. **Get the PDF in, once.** Local file: `request_upload`, run the `curl`
   command, keep the `image_id`. Public link: pass `image_url` to `pdf_pages`
   (or `open_image`); the reply names the `image_id` the server stored it
   under. From then on use that `image_id` only. Never upload, download, or
   paste the file again to reach another page.
2. **Find the page.** `pdf_pages(image_id=…)` is free and returns the page
   count plus the size and opening text of each page.
   - `pages="12"` returns that page's full text; `pages="10-20"` lists a range.
   - `previews=true` adds a sheet of thumbnails (12 pages per call). Use it for
     scans and drawing sets, where pages have no text layer.
   - If the user already named a page ("the SLD on page 4"), skip this step.
3. **Open only that page.** `open_image(image_id=…, page=N)` renders page N
   and starts a session on it.
4. **Zoom as usual** on that page until every value is sharp.
5. **Next page:** `open_image(image_id=…, page=M)`. Each page is its own
   session; older sessions close on their own.

Rules:

- The page text and thumbnails are for **choosing** a page. Values you report
  must still be read from a zoomed view, because drawings and scans often carry
  no text layer, or an incomplete one.
- Page numbers are 1-based positions in the file, which can differ from the
  number printed on the sheet ("E-201", "Page 3 of 9"). Tell the user which you
  mean, and say which page every value came from.
- Finish a page before opening the next, and keep notes as you go: you cannot
  see a page you have left.
- For a document question ("find the certificate number"), list the pages
  first and open only the ones that can hold the answer, instead of opening
  every page.
- Uploads are kept for an hour. If an `image_id` has expired, send the file
  once more and continue from the page you were on.

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

---
name: engineering-drawings
title: Engineering drawings & single-line diagrams
description: Reading electrical single-line diagrams, architectural and mechanical sheets, title blocks, schedules, and revision tables.
---

# Engineering drawings & single-line diagrams

Read `zoom-basics` first. This adds the reading order and the traps specific to
technical drawings.

## Drawing sets (multi-page PDFs)

A set is sent once and opened sheet by sheet by page number. Call
`pdf_pages(image_id=…, previews=true)` to see every sheet as a thumbnail (sets
are often scans with no text), find the sheet you need, usually from a drawing
index on the first pages, then `open_image(image_id=…, page=N)`. Report both
the PDF page number and the sheet number from the title block. Details are in
`long-documents`.

## Reading order

1. **Title block** — usually the bottom-right corner or a strip down the right
   edge. Zoom there first: project, sheet title, sheet number, revision, date,
   scale, and the engineer's seal tell you what the sheet is and whether it is
   the issue you expect (IFC, as-built, redline).
2. **Legend, general notes, abbreviations** — typically along the right side or
   in a corner. Symbols and abbreviations differ between firms; resolve them
   from the sheet's own legend, not from memory.
3. **Schedules and tables** (panel, equipment, cable, conductor, module). Zoom
   to the header row first, then go through the body in bands of a few rows.
   Keep the column headers in view or re-read them when you move down.
4. **The body of the drawing**, following the flow rather than scanning at
   random.

## Single-line diagrams

- Follow the power path in one direction: source or utility → transformer →
  switchgear / main breaker → feeders → loads (or, for generation: array →
  combiner → inverter → disconnect → meter → point of interconnection).
- Each device normally has a tag plus a small stack of ratings next to it
  (amps, volts, poles, kAIC, kVA, impedance). Zoom until every line of that
  stack is sharp; ratings are the most commonly misread values.
- Conductor callouts (`3#4/0 + 1#2 GND in 2" C`) are dense. Read them at factor
  5–6 and copy them character for character.
- When a line leaves the view, note the cell where it exits, `undo`, and pick it
  up in the neighbouring cells. Do not assume where it goes.
- Counts ("how many inverters / strings / breakers") must come from tagging each
  one as you read it, not from an impression of the overview.

## Plans and layouts

- Dimensions belong to the dimension line they sit on; check which witness lines
  they span before reporting them.
- Check the scale and north arrow before interpreting distances or orientation.
- Revision clouds and deltas mark what changed. Read the revision table to
  match a delta number to its description and date.

## Reporting

- Quote values exactly as drawn, including units and tolerances.
- Cite where each value came from (for example "panel schedule, rows 4–6" or
  "title block") so a person can check it quickly.
- If two places on the sheet disagree (schedule vs. diagram), report both and
  flag the conflict instead of choosing one.
- Handwritten redlines override printed values only if the user asked for the
  as-marked state; otherwise report both.

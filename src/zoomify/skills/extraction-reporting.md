---
name: extraction-reporting
title: Verified extraction & reporting
description: Turning what you read into a trustworthy answer or structured JSON, with sources, confidence, and explicit gaps.
---

# Verified extraction & reporting

Read `zoom-basics` first. Use this when the user wants data out of an image —
a list, a table, or JSON — rather than a description.

## Before you start

- Restate the fields you are going to extract. If the user gave a schema, use
  its field names exactly.
- Decide where each field is likely to live (title block, schedule, body) so
  you can plan your zooms instead of wandering.

## While reading

Keep a working table as you go:

| Field | Value | Where | Confidence |
|---|---|---|---|
| sheet_number | E-201 | title block | read clearly |
| main_breaker_rating | 400 A | SLD, main switchboard | read clearly |
| inverter_count | 6 | SLD, tagged INV-1…INV-6 | counted individually |
| issue_date | — | title block | illegible after 6x zoom |

## Output rules

- Every value must have been read at a zoom level where it was sharp.
- Unknown is a valid value. Use `null` (or the user's stated placeholder) plus a
  note; never fill a gap with a plausible guess.
- Keep units and formatting as drawn (`480Y/277V`, `1/2"`, `2017-03-14`), unless
  the user asked for normalisation — then give both the raw and normalised form.
- Numbers: preserve leading zeros and precision.
- Flag conflicts between two places on the document instead of resolving them
  silently.

## Structured JSON

When JSON is requested, return one object matching the requested schema, and
add a parallel `_sources` object (field → where it was read) and a
`_unresolved` list (fields you could not read, with the reason) unless the user
asked for the schema only.

## Final check

Before answering, re-zoom the two or three values that matter most (totals,
ratings, IDs) once more from the root view. A second independent read catches
most transcription slips.

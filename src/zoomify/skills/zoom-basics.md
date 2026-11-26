---
name: zoom-basics
title: Zoom basics
description: Core workflow for reading any large, dense, or tiny-font image with the grid and zoom tools. Read this first.
---

# Zoom basics

Vision models skim. A full drawing, map, or long screenshot is downscaled before
you see it, so small labels are blurred or invented. Zoomify fixes that by
letting you look the way a person does with a PDF viewer: overview first, then
magnify the parts that matter.

## The loop

1. **Open** the image with `open_image`. You get a `session_id` and the full
   image with a labeled grid: columns are letters (`A`, `B`, …) along the top
   and bottom, rows are numbers (`1`, `2`, …) along the sides.
2. **Locate.** Decide which cells contain what you need. Do not read values from
   the overview — it is only good enough for finding where things are.
3. **Zoom** into those cells with `zoom`. The crop is upscaled and given a fresh
   grid, so you can zoom again to go deeper.
4. **Read and record** what you can now see clearly, with the cell it came from.
5. **Navigate**: `undo` to step back one level, `restore` to return to the full
   image, then zoom somewhere else. Repeat until the question is answered.

## Getting the image in

The server runs in the cloud and cannot read files on the user's machine. Pick
the source that matches what you were given:

| You have | Do this |
|---|---|
| A public `https://` link | `open_image(image_url=…)` |
| A file on disk | `request_upload(file_path=…)`, run the `curl` command it returns in your shell, then `open_image(image_id=…)` |
| An `image_id` (`img_…`) | `open_image(image_id=…)` |
| A small image already in memory and no shell | `open_image(image_base64=…)` |
| A multi-page PDF (any of the above) | Send it once, then `pdf_pages(image_id=…)` to pick a page and `open_image(image_id=…, page=N)` to open it — see `long-documents` |

The upload link from `request_upload` needs no API key, works once, and expires
in 15 minutes. Never search for, read, or ask for the user's Zoomify API key,
and do not paste a file's base64 into a tool call when you can upload it from
disk instead: the upload costs no tokens. If you have neither a shell nor the
image bytes, ask the user for a public link or to upload the file on the
Zoomify Connect page and give you the `image_id`.

## Selecting cells

| You want | Write | Meaning |
|---|---|---|
| One cell | `C2` or `2C` | column C, row 2 |
| A rectangle | `1-3-B-E` | rows 1 to 3, columns B to E |
| Several cells | `1C,3B,4C` | bounding box around all of them |
| Several regions | `1-2-A-F, 3-5-G-J` | bounding box around all of them |

Labels always refer to the **current** view. After every zoom the grid is new —
never reuse a cell name from a previous view.

## Choosing the zoom factor

- `3` (default) suits most text.
- `4`–`6` for tiny fonts, stamps, dimension strings, subscripts.
- Prefer a **small selection with a high factor** over a big selection. If the
  selection is large the server lowers the factor and tells you; pick fewer
  cells instead.
- Text cut off at the edge of a view? `undo` and select one more row or column.

## Rules that keep you accurate

- **Only state what you have read at a zoom level where it is sharp.** If it is
  still unreadable after two deeper zooms, say so; do not guess.
- **You only see the current view.** Anything you left is gone from sight — note
  values down as you read them.
- **Easily confused glyphs** (`0/O`, `1/I/l`, `5/S`, `8/B`, `3/8`): zoom once
  more and compare against the same character elsewhere on the sheet.
- **Cover the whole area you were asked about.** Work through it in a fixed
  order (left to right, top to bottom) so nothing is skipped.
- **Wrong region?** `undo` is free. Only `open_image` and `zoom` count against
  the request allowance, so backing out never costs anything.

## Quota

`usage` shows the plan, requests left this month, and the per-minute limit. If a
call is refused for the rate limit, wait a few seconds and retry. If the monthly
allowance is exhausted, tell the user — they can upgrade on the Zoomify pricing
page.

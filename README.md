# 🔆 Zoomify — Image Detail Extraction Agent

**Vision LLMs are bad at reading whole images when the detail matters.**

Send a blueprint, site map, engineering diagram, long desktop screenshot, dense
dashboard, or any large info graphic to GPT-4o (or similar) in one shot and it
will miss labels, invent values, or skim past the tiny parts — small UI icons,
footnote text, legend entries, breaker ratings, parcel IDs, and table cells that
only become readable when you zoom in. The model sees the full frame at once;
it does not naturally pan, magnify, and re-read the way a human would with a
PDF viewer.

**Zoomify is a helper agent for exactly that.** Upload the image, ask a question,
and an OpenAI vision model navigates a **labeled grid** — cropping, upscaling,
and re-gridding regions until it can read the small print. It works like a
human using zoom on a site plan or SLD: start at the overview, drill into the
cells that matter, back out and retry if the wrong area was picked.

Built for coders who need to **extract structured data from images models
normally fail on**:

- **Blueprints & single-line diagrams** — electrical, mechanical, architectural
- **Site maps & parcel plans** — boundaries, labels, legend text
- **Large desktop / app screenshots** — toolbars, status bars, small icons
- **Long scrolling captures** — chat logs, tables, multi-panel UIs
- **Posters, scans, and dense infographics** — mixed font sizes on one canvas

Zoomify is a **Gradio app** plus a small **grid + zoom tool library** you can
reuse in your own pipelines. The agent auto-grids the upload, walks a branching
**zoom tree**, and answers from what it actually read — not from a blurry
first glance.

## Tools

| Tool | What it does |
|------|--------------|
| **zoom** | Crops a selected cell/region (e.g. `2C`, `1-3-B-E`) from the current image, upscales it, and re-grids it. Branches to a (new or cached) child node and makes it current. |
| **undo** | Moves the pointer to the **parent** image (e.g. to retry a different region after a wrong zoom). |
| **redo** | Moves the pointer **forward** to the child you last backed out of. |
| **restore** | Jumps the pointer back to the **root** — the full auto-gridded image. |

The pointer marks the single image currently being processed. Zooms form a
**branching tree (DAG)**: zooming the wrong region, then `undo`-ing to the parent
and picking a different one creates a new branch — so wrong guesses are cheap to
back out of. Because the chess-grid choices are finite, the tree is also a
**cache**: re-selecting a region already explored from a node jumps straight to
that existing branch instead of recomputing. The grid/zoom engine lives in two
files — `src/zoomify/gridder.py` (grid overlay, used to auto-grid + re-grid) and
`src/zoomify/gridzoom.py` (crop + zoom + re-grid).

## Project layout

```
Zoomify/
├── pyproject.toml          # uv project
├── .env.example            # OPENAI_API_KEY, OPENAI_MODEL
├── app.py                  # Gradio entrypoint
├── "Example Files"/         # sample images (Aviva electrical SLD, etc.)
└── src/zoomify/
    ├── gridder.py          # grid engine: auto-grid + re-grid primitives
    ├── gridzoom.py         # crop + zoom + re-grid
    ├── tools.py            # tool schemas, history-stack image state, dispatch
    └── agent.py            # OpenAI vision + tool-calling loop
└── tests/                  # pytest suite (gridder/gridzoom/tools/agent/app)
```

## Setup (uv)

Install [`uv`](https://docs.astral.sh/uv/) (`brew install uv` or
`curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
uv sync                     # creates .venv/ and installs dependencies
cp .env.example .env        # then edit .env and add your OPENAI_API_KEY
```

## Run

```bash
uv run python app.py
```
Open the printed local URL. On the **left** is the chat: use the **+** button to
attach an image (images only) and **Send** your prompt — for example:

> *Read the footer of this screenshot and list every link and status message.*

or, for a site-map:

> *What is the total DC capacity and how many inverters are shown? Zoom into the
> legend to read the labels.*

A one-click **example** (the Aviva electrical single-line diagram) is provided
for free experimentation. The
**right** panel shows the zoom **tree (DAG)** as a vertical layout — root at top,
zoom branches flowing downward — with the current node highlighted `◀ current`,
so you can follow (and see) the agent's drill-down. **Click any node thumbnail**
to open a larger image preview; close it with the **✕** button (or by clicking
outside the image). While the agent is working the input is **locked** and a
**⏹ Stop** button appears — click it to cancel the in-flight run and re-enable
input.

## How it works

1. On upload, the image is **auto-gridded** (labeled columns `A..`, rows `1..`)
   and becomes the **root** of a zoom tree.
2. The model identifies which cells hold the requested information.
3. It calls `zoom` (raise `zoom`/`regrid_cols` for tiny fonts) to read the
   detail, drilling down repeatedly — each zoom re-grids the crop and branches
   to a child node.
4. It can `undo` (to the parent) to retry a different region after a wrong guess,
   `redo` to step forward again, or `restore` to jump back to the full image.
   Re-selecting a region already explored from a node is **cached** — the agent
   jumps to the existing branch instead of recomputing.

Because the Chat Completions API can't embed images in `tool` messages, each
tool result is returned as a text status plus a follow-up multimodal `user`
message carrying the processed image, so the model can actually see it. Only the
**single most recent image** (the current pointer) is kept in context — older
images are replaced with a text placeholder — so the model must genuinely
navigate (`undo` / `redo` / `restore` / `zoom`) to revisit a node rather than
relying on remembered images. As it navigates, the right-hand tree updates
**live**, so you can watch the `◀ current` pointer travel through the DAG in
real time.

## Configuration

Set in `.env`:

- `OPENAI_API_KEY` — your OpenAI key.
- `OPENAI_MODEL` — any vision + tool-calling model (default `gpt-4o`).

## Tests

The image tools, the agent loop (mocked OpenAI client) and the Gradio handlers
are covered by a pytest suite:

```bash
uv sync --group dev                                # install pytest + pytest-cov
uv run python -m pytest                            # run the suite
uv run python -m pytest --cov=zoomify --cov=app    # with coverage
```

No API key is required — the agent tests drive a scripted fake OpenAI client.

## License

Zoomify is released under the **[MIT License](LICENSE)**.

You are free to use, modify, and ship this code in your own projects — commercial
or open source — as long as you **keep the copyright notice and license text**
and **give credit to [Zynclo Softwares](https://github.com/Zynclo-Softwares)**.
A link back to this repository or a mention in your docs or README is enough.

See [CONTRIBUTING.md](CONTRIBUTING.md) if you want to send a pull request.

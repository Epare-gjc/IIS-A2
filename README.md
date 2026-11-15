# LitLens — evidence-first literature Q&A

Prose word count: 996 (headings, code blocks, tables of file names and setup commands excluded).

LitLens answers questions about a small, fixed set of reading notes on filter bubbles, recommender
explanations and interaction design. Every answer is built from retrieved passages, cites them as
`[S1]`, and is refused when nothing in the corpus is close enough. The model is DeepSeek
`deepseek-flash` over its OpenAI-compatible HTTP API.

This repository contains the Assignment 2 project: the running system, its tests, the report
(`docs/report/A2_Project_Report.docx`) and the report figures (`docs/report/figures/`).

## Status

Works and was run in a browser:

- bilingual retrieval over 17 paraphrase notes (TF-IDF, CJK character bigrams, author/title aliases)
- the refusal gate: best score below `0.15` returns a measured refusal without calling the model
- evidence-only mode, which shows the passages and scores and never calls the model
- citation whitelist: `[S4]` in a model answer when only three passages were sent is removed and reported
- streaming answer text, per-turn run log (`logs/runlog.csv`), CSV download from the sidebar
- 27 unit tests, a calibration script and a command-line runner

Not verified: a live grounded answer end to end. No API key is stored in this repository, so the
generation path was checked up to the HTTP layer only — an invalid key returns the mapped
`API key 无效或已过期` error, which shows the request reached DeepSeek. Add your own key to see
an answer (see below).

Simulated: nothing is faked. The screenshots in `docs/report/figures/` are captures of the running
app; the storyboard figures redraw states that were actually produced, and the refusal in them was
produced by the real gate.

Planned, not built: uploading your own PDFs, sentence-level highlighting of the supporting span, a
participant study comparing judgements with and without the evidence panel.

## Technology stack

| Piece | What it does | Why this |
| --- | --- | --- |
| Python 3.11+ (3.14 tested) | runtime | course default |
| Streamlit ≥ 1.49 | the whole interface: chat input, expanders, sidebar controls, CSV download | one file, no front-end build, easy for a marker to run |
| `litlens/retrieval.py` | TF-IDF ranking, no third-party dependency | small corpus, and the scoring stays readable |
| `urllib` (stdlib) | HTTPS + SSE request to DeepSeek | keeps the project to one dependency and makes the request body inspectable |
| DeepSeek `deepseek-flash` | writes the answer from the numbered passages, thinking mode disabled | cheap, fast, and a documented OpenAI-compatible endpoint |
| `unittest` | 27 tests over retrieval, citations, prompt and service | runs with no extra install |

No API key is committed. `.env.example` shows the two variables.

## Run it

```bash
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt
cp .env.example .env                               # then paste your DEEPSEEK_API_KEY
streamlit run app.py
```

Without a key the app still runs: the toggle starts in evidence-only mode and the sidebar says why.

Command line, no browser:

```bash
python scripts/ask.py "什么是信息茧房？" --evidence-only
python scripts/ask.py --demo                       # five questions, one of them unanswerable
python -m unittest discover -s tests -t .          # 27 tests
python scripts/calibrate.py                        # score spread and the threshold it implies
```

## What to try

- `什么是信息茧房？` → two passages, `[S1]` expands to the note in English and Chinese.
- `TasteWeights 让用户调整什么？` → the source alias routes the question to the right paper.
- `今天北京天气怎么样？` → refused, `0.000 < 0.15`, no request sent.
- Turn the toggle off with a key configured → a streamed answer with `[S1]` citations and the same
  evidence panel left open beside it.

## How an answer is produced

1. The question is tokenised (ASCII words plus CJK character bigrams) and ranked against 17 notes.
2. The best cosine score plus a `0.20` alias boost decides the gate; below `0.15` the turn stops.
3. Survivors are numbered `[S1]…[S3]` and sent with six rules that forbid outside knowledge.
4. The streamed reply is checked against the identifiers actually sent; invented ones are stripped.
5. The turn is appended to the run log with scores, mode, latency and removed citations.

## Development record

The stages below are the commits; each entry says what changed, why, and what was checked.

| Stage | Commit | Change and reason | Checked by |
| --- | --- | --- | --- |
| D1 | [data]({COMMIT_D1}) | 17 paraphrase notes, bilingual, versioned in the repo | passage count and duplicate ids asserted on load |
| D2 | [retrieval]({COMMIT_D2}) | TF-IDF retriever; first version was single CJK characters | ranking inspected by hand on ten questions |
| D3 | [calibration]({COMMIT_D3}) | bigrams, stopword list, source aliases, threshold `0.15` | gap `0.003 → 0.077`, 10/10 source match, `scripts/calibrate.py` |
| D4 | [citations]({COMMIT_D4}) | prompt rules and the citation whitelist | 9 citation cases and prompt numbering tests |
| D5 | [llm]({COMMIT_D5}) | stdlib HTTPS client replacing the OpenAI SDK | invalid key → mapped `401` message, no crash |
| D6 | [service]({COMMIT_D6}) | generator pipeline, gate before the model call, run log | refusal-before-generation and logging tests |
| D7 | [ui]({COMMIT_D7}) | Streamlit page: evidence panels, refusal card, run log export | run in a browser at 1264×805, screenshots kept |
| D8 | [docs]({COMMIT_D8}) | README, design notes, superseded Assignment 1-adjacent plan | links and commands re-run from a clean shell |
| D9 | [report]({COMMIT_D9}) | report builder, figures, storyboards | LibreOffice render of all five pages |

Two changes came from failure rather than planning. The single-character index flattened every score
until the threshold was meaningless, so Chinese is now indexed as bigrams with a stopword list. The
OpenAI SDK was dropped after `pip install openai` was blocked in this environment and the thin
`urllib` client turned out to be easier to audit; the project now needs one dependency.

`docs/design.md` has the longer pipeline note, the verbatim prompt rules and the failure log.

## AI assistance

- **In the product:** the app calls DeepSeek `deepseek-flash` for the answer text. It is given only the
  retrieved passages and is not trusted: the citation check and the refusal gate are ordinary Python.
- **In development and writing:** an AI assistant (DeepSeek Harness agent) drafted the module
  skeletons, the tests, the README and the report text. Every threshold, number and claim in the
  report was re-measured by running `scripts/calibrate.py`, the test suite and the app; the assistant's
  first storyboard draft invented a `latency_ms=0` log line and it was replaced with the field the
  system actually writes.

## Additional files

- `docs/report/A2_Project_Report.docx` — the submitted report; figures live beside it.
- `docs/report/figures/` — app screenshots, the storyboard sheet, the system diagram, and the HTML
  sources used to render the two diagrams.
- `docs/design.md` — pipeline, prompt text, failure log.
- `docs/superseded/` — an earlier plan for a different system, kept for the record.
- `scripts/build_report.py` — regenerates the report from its text and figures.

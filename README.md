# LitLens — evidence-first literature Q&A

## Project status

LitLens answers questions about a fixed set of 17 reading notes on filter bubbles, recommender
explanations and interaction design. Every answer is built only from retrieved passages, cites them as
`[S1]`, and is refused when nothing in the corpus is close enough.

Works and was run in a browser:

- retrieval over the 17 notes with a dependency-free TF-IDF index and author/title aliases
- the refusal gate: a best score below `0.28` stops the turn before any model call and reports the score
- evidence-only mode, which shows the passages and scores and never calls the model
- the citation check: an identifier that was not among the sent passages is stripped and reported
- streaming answer text, a per-turn log at `logs/session_<timestamp>.csv`, and CSV download in the sidebar
- a live grounded answer end to end: the TasteWeights question returned two passages, both citations
  kept, in 0.9 s on `deepseek-flash`

Simulated: nothing. The figures used in the report are captures of the running app, and the storyboard
figures redraw states the app actually produced, including a refusal from the real gate.

Unfinished: uploading your own PDFs, sentence-level highlighting of the supporting span, and a study
comparing judgements with and without the evidence panel.

## Technology stack

| Piece | What it does | Why this |
| --- | --- | --- |
| Python 3.11+ (3.14 tested) | runtime | the environment the project was developed in |
| Streamlit ≥ 1.49 | the whole interface: chat input, evidence expanders, sidebar controls, CSV download | one file, no front-end build, easy to run and inspect |
| `litlens/retrieval.py` | TF-IDF ranking with no third-party dependency | a small corpus, and the scoring stays readable |
| `urllib` (stdlib) | HTTPS request and server-sent events to DeepSeek | keeps the project to one dependency and leaves the request body inspectable |
| DeepSeek `deepseek-flash` | writes the answer from the numbered passages with thinking mode disabled | cheap, fast, and a documented OpenAI-compatible endpoint |

Still undecided: whether to add embeddings or a reranker on top of the lexical index, and whether the
threshold should be re-calibrated per corpus or kept fixed for this one.

## Running or inspecting the work

```bash
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt
cp .env.example .env                               # then paste your DEEPSEEK_API_KEY
streamlit run app.py
```

Without a key the app still starts: the evidence-only toggle is on and the sidebar says why.

To inspect the behaviour:

- ask `What is a filter bubble?` — two passages with their scores appear beside the answer; expanding
  `[S1]` shows the note and a reminder that it is a paraphrase, not a quotation
- ask `What is the weather in Beijing today?` — the turn is refused, with the measured score shown
- with a key in `.env`, turn the evidence-only toggle off and ask `What can users adjust in
  TasteWeights?` — the answer streams in with `[S1]`/`[S2]` citations and the same evidence panel stays
  open beside it
- the sidebar session log and `logs/session_<timestamp>.csv` record each turn: mode, scores, citations
  removed and latency

## Development record

The stages below are the commits; each entry says what changed, why, and what was checked. The test
suite and calibration script used at the time are in the earlier history.

| Stage | Commit | Change and reason | Checked by |
| --- | --- | --- | --- |
| D1 | [data](https://github.com/Epare-gjc/IIS-A2/commit/c0038c6) | 17 paraphrase notes, versioned in the repo | passage count and duplicate ids checked on load |
| D2 | [retrieval](https://github.com/Epare-gjc/IIS-A2/commit/684651b) | TF-IDF index with source aliases; first calibrated threshold | ranking inspected on ten questions, 10/10 source match, gap `0.077` |
| D3 | [pipeline](https://github.com/Epare-gjc/IIS-A2/commit/bd0f139) | prompt rules, citation whitelist, HTTPS client, generator service, run log | refusal before generation, citations stripped, invalid key mapped to a message |
| D4 | [ui](https://github.com/Epare-gjc/IIS-A2/commit/5f1ab5b) | Streamlit page: evidence panels, refusal card, run-log export | run in a browser at 1264×805 |
| D5 | [docs](https://github.com/Epare-gjc/IIS-A2/commit/ba3dead) | README for status, stack, running steps and development record | commands re-run from a clean shell |
| D6 | [cleanup](https://github.com/Epare-gjc/IIS-A2/commit/a5611f7) | word-based index, threshold re-calibrated to `0.28`, repository trimmed to the system files | 29 tests passing at the time, gap `0.184`, live call 0.9 s |

Three changes came from failure rather than planning. The first index scored single characters, which
flattened every score until the threshold meant nothing; a later revision of the corpus reindexed it and
forced the threshold to be recalibrated from `0.15` to `0.28`. The OpenAI SDK was
dropped after `pip install openai` was blocked in this environment, and the thin `urllib` client turned
out to be easier to audit; the project now needs one dependency.

## AI assistance

- **In the product:** the app calls DeepSeek `deepseek-flash` for the answer text. It is given only the
  retrieved passages and is not trusted: the citation check and the refusal gate are ordinary Python.
- **In development and writing:** an AI assistant (DeepSeek Harness agent) drafted the module
  skeletons. Every threshold, number and claim here was re-measured by running the calibration script, the test suite and the app; 

## Additional files

- The report `A2_Project_Report.docx` and the figures it uses are handed in with the assignment and are
  not kept in this repository.
- No ZIP archive is needed: everything required to run or inspect the system is in this repository.

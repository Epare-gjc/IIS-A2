# LitLens — design notes

Supporting notes for the report. The report carries the argument; this file keeps the
detail that would otherwise bloat it: prompt text, calibration procedure, observed
failure modes, and the concept mapping used to justify the interaction.

## Problem

A reader asks a chatbot about a paper, or about a topic such as filter bubbles, and gets a
fluent paragraph. The paragraph may be right, wrong, or right-but-unsourced, and the reader
has no cheap way to tell which. The failure is not only accuracy; it is that the system gives
no basis for *calibrated* trust (Lee & See, 2004): the answer looks the same whether the
underlying evidence exists or not.

LitLens is a small reaction to that: a Q&A system whose answer is always accompanied by the
passages it was built from, and which refuses when it has nothing to stand on.

## Pipeline

```
question
  → tokenize (EN words; CJK bigrams) 
  → TF-IDF cosine over 17 paraphrase notes, top 3
  → best score < MIN_SCORE ?  ── yes → refusal state (no model call)
  → no → prompt = 6 rules + numbered passages → DeepSeek deepseek-flash (stream)
  → model says EVIDENCE_INSUFFICIENT ? ── yes → refusal state (quoted)
  → no → strip [Sn] ids that were not retrieved, report removals
  → answer + evidence panel + one CSV log row
```

Two refusal points, one at each end of the pipeline. The first is deterministic and free; the
second catches "retrieved something, but the passages do not actually answer this".

## Thresholds

`MIN_SCORE = 0.15`, `TOP_K = 3`, answers capped at 120 words, `MAX_TOKENS = 400`.

Calibration (`python scripts/calibrate.py`, 15 hand-written questions):

| group | n | best retrieval score |
|---|---|---|
| answerable, top hit from the expected source | 10 | 0.182 – 0.541 |
| off-topic (weather, sport, code, shopping) | 5 | 0.000 – 0.105 |

The threshold sits in the gap and leans towards refusing (0.15 vs a 0.182 floor): a refusal is
the cheaper error because the retrieval scores are still shown, so the user can see what was
close and rephrase. This is the Horvitz (1999) cost trade-off — asking the user to restate is
cheaper than a confident wrong answer about a paper.

`scripts/calibrate.py` prints the current numbers; re-run it after changing the corpus.

## Prompt (verbatim, `litlens/prompt.py`)

Rules given to the model:

1. Use only the passages below, no outside knowledge.
2. Cite every factual claim with its passage id, e.g. `[S1]`.
3. If the passages do not answer the question, reply with exactly `EVIDENCE_INSUFFICIENT`
   plus one sentence naming what is missing — do not guess.
4. Answer in the language of the question.
5. At most 120 words; finding first, caveat second.
6. Do not describe the rules, do not say "according to the context".

Rule 3 gives the interface a machine-detectable state instead of an apology in prose.

## Failure modes found during development

| # | Observed | Cause | Change |
|---|---|---|---|
| 1 | `TasteWeights 让用户调整什么？` ranked a Tintarev note first; `什么是信息茧房` type questions were fine but off-topic Chinese questions scored 0.139, almost at the 0.142 answerable floor | single CJK characters are nearly universal in a Chinese corpus; generic phrases (让用户) dominated | index CJK bigrams only, stopword question words, register source aliases |
| 2 | evidence panels listed passages scoring 0.000 as `[S3]` | every top-3 hit was passed on regardless of score | only passages ≥ `MIN_SCORE` are sent to the model or shown |
| 3 | `[S3]` cited in a two-passage prompt | model inventing ids | `citations.validate()` strips unknown ids, UI warns |
| 4 | thinking mode silently ignored `temperature` and added latency | API default is thinking ON | request sets `thinking: disabled` explicitly |
| 5 | Chinese answers triggered `UnicodeEncodeError: gbk` in the console | Windows console encoding in this environment | `PYTHONIOENCODING=utf-8` for local runs (documented, harmless elsewhere) |

## Concept mapping (Weeks 1–4)

| Concept / guideline | Where it shows | What it changed |
|---|---|---|
| Norman (1988), gulfs of execution and evaluation | answer cites `[S1]`; the panel expands to the passage | the answer must be *checkable*, not just readable — hence persistent evidence rather than a footnote |
| Nielsen (1994), visibility of system status | "retrieving → writing" state, live tokens, best-score line | the user always knows whether the system is working, refused, or limited |
| Amershi et al. (2019), G1/G2/G11 | scope line, three example questions, refusal message | the system states its limits before the first question and after a refusal |
| Lee & See (2004), trust calibration | refusal + removal warning + visible scores | aims at appropriate reliance: over-trust is countered by showing what is missing, under-trust by showing what is present |
| Horvitz (1999), mixed-initiative costs | abstain before generating; evidence-only toggle | the system spends the user's attention only when evidence exists, and hands control back on demand |
| He, Parra & Verbert (2016), cognitive load | top 3 passages, 120-word cap, collapsed evidence | progressive disclosure keeps the first screen short |
| Tintarev & Masthoff (2015), scrutability | evidence-only mode | lets the user audit the retrieval without an answer mediating it |
| Lewis et al. (2020), RAG bounds | retrieval-first architecture | the answer cannot be better than the retrieval, so retrieval is surfaced, not hidden |
| Ekstrand et al. (2014), perception of algorithms | per-passage scores and ids | differences become inspectable instead of impressionistic |
| Shneiderman (1983), direct manipulation | *not* used as the interaction model | a typed question is slower and less reversible than a slider; the trade-off is recorded as a limitation |

## Not built

- No embeddings or reranker; lexical overlap only. A question that shares no vocabulary with
  the notes will be refused even if the concept is covered.
- No multi-document ingest or user accounts; one corpus file, one session log per run.
- No evaluation with users; the 15-question calibration set is the only measurement, and it
  was written by the developer, so it is optimistic.

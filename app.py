"""LitLens -- evidence-first literature Q&A (Streamlit interface).

Run with:  streamlit run app.py

Every answer is built from the passages shown beside it. When retrieval cannot
find a passage above the calibrated threshold the system refuses *before* calling
the model, so a refusal never costs a request and never invents content.
"""

from __future__ import annotations

import streamlit as st

from litlens import config, corpus, llm, runlog, service

st.set_page_config(
    page_title="LitLens - evidence-first literature Q&A",
    page_icon="🔎",
    layout="wide",
)

# Keep screenshots and the deployed view free of Streamlit's own chrome.
st.markdown(
    "<style>[data-testid='stToolbar']{display:none;} #MainMenu{visibility:hidden;}"
    "footer{visibility:hidden;}</style>",
    unsafe_allow_html=True,
)

EXAMPLES = [
    "什么是信息茧房？",
    "TasteWeights 让用户调整什么？",
    "用户的信任应该如何校准？",
    "How many guidelines does Amershi propose for human-AI interaction?",
    "今天北京天气怎么样？",
]


def compact(hits: list[dict]) -> list[dict]:
    """Flatten passages for session history (keeps replays cheap)."""
    out = []
    for h in hits:
        raw = h["doc"]["raw"]
        out.append(
            {
                "id": h["id"],
                "score": h["score"],
                "source": raw["source"],
                "year": raw["year"],
                "en": raw["en"],
                "zh": raw["zh"],
            }
        )
    return out


def evidence_panel(turn: dict) -> None:
    st.caption(
        f"Best retrieval score {turn['best']:.3f} · refusal threshold "
        f"{config.MIN_SCORE:.2f} · {len(turn['hits'])} passage(s) used"
    )
    for i, hit in enumerate(turn["hits"], start=1):
        with st.expander(f"[S{i}] {hit['source']} — score {hit['score']:.3f}"):
            st.markdown(f"**EN** · {hit['en']}")
            st.markdown(f"**ZH** · {hit['zh']}")
            st.caption(
                "Paraphrase note written for this project, not a quotation. "
                f"Passage id {hit['id']}."
            )


def render_body(turn: dict, box) -> None:
    kind = turn["kind"]
    if kind == "final":
        box.markdown(turn["answer"])
    elif kind == "abstain":
        box.warning(
            f"**No answer.** The best passage scored {turn['best']:.3f}, below the "
            f"{config.MIN_SCORE:.2f} threshold, so the model was not called. "
            "Rephrase the question, or use evidence-only mode to read the closest "
            "passages and judge them yourself."
        )
    elif kind == "error":
        box.error(turn["answer"])
    elif kind == "insufficient":
        box.info(
            "**The model judged the retrieved passages insufficient.** It was "
            "instructed to say so instead of answering from general knowledge: "
            f"\n\n> {turn['answer']}"
        )
    else:
        box.caption(
            "Evidence-only mode: the model was not called. Read the passages and "
            "judge them yourself."
        )

    if turn["removed"]:
        ids = ", ".join(f"S{n}" for n in turn["removed"])
        st.warning(
            f"Removed {len(turn['removed'])} citation(s) the model invented "
            f"({ids}); those passages were never retrieved."
        )
    if turn["hits"]:
        evidence_panel(turn)
    if kind == "final" and turn.get("latency_ms"):
        st.caption(f"{turn['latency_ms']} ms · model {config.MODEL}")


def run_turn(question: str, evidence_only: bool, log) -> None:
    with st.chat_message("user"):
        st.markdown(question)

    turn = {
        "question": question,
        "kind": "final",
        "answer": "",
        "hits": [],
        "best": 0.0,
        "removed": [],
        "latency_ms": 0,
        "evidence_only": evidence_only,
    }
    with st.chat_message("assistant"):
        box = st.empty()
        streamed = ""
        for event in service.ask(question, evidence_only=evidence_only, log=log):
            kind = event["type"]
            if kind == "evidence":
                turn["best"] = event["best"]
                turn["hits"] = compact(event["hits"])
            elif kind == "delta":
                streamed += event["text"]
                box.markdown(streamed + "▌")
            elif kind == "final":
                turn["answer"] = event["text"]
                turn["removed"] = event["removed"]
                turn["latency_ms"] = event["latency_ms"]
            elif kind == "abstain":
                turn["kind"] = "abstain"
            elif kind == "insufficient":
                turn["kind"] = "insufficient"
                turn["answer"] = event["text"]
            elif kind == "evidence_only":
                turn["kind"] = "evidence_only"
            elif kind == "error":
                turn["kind"] = "error"
                turn["answer"] = event["message"]
        render_body(turn, box)

    st.session_state["history"].append(turn)


# --- session state -----------------------------------------------------------
st.session_state.setdefault("history", [])
if "log" not in st.session_state:
    st.session_state["log"] = runlog.RunLog.new()
if "conn" not in st.session_state:
    st.session_state["conn"] = None
log = st.session_state["log"]

# --- sidebar -----------------------------------------------------------------
with st.sidebar:
    st.subheader("Status")
    if config.has_api_key():
        st.success(f"API key found · model `{config.MODEL}`")
    else:
        st.warning("No `DEEPSEEK_API_KEY`. Retrieval and refusal still work.")
    if st.button("Test connection", width="stretch"):
        ok, message = llm.check_connection()
        st.session_state["conn"] = (ok, message)
    if st.session_state["conn"] is not None:
        ok, message = st.session_state["conn"]
        st.caption(("✅ " if ok else "⚠️ ") + message)

    evidence_only = st.toggle(
        "Evidence-only mode (no model call)", value=not config.has_api_key()
    )
    st.caption(
        f"TOP_K {config.TOP_K} · MIN_SCORE {config.MIN_SCORE:.2f} · "
        f"answer ≤ {config.ANSWER_MAX_WORDS} words"
    )

    st.divider()
    passages = corpus.load_passages()
    with st.expander(f"Corpus: {len(passages)} paraphrase notes"):
        st.dataframe(
            [
                {
                    "id": p["id"],
                    "source": p["source"].split(". ")[0] + "…",
                    "year": p["year"],
                    "tags": ", ".join(p.get("tags", [])),
                }
                for p in passages
            ],
            width="stretch",
            hide_index=True,
            height=260,
        )
        st.caption(
            "Paraphrase notes, not verbatim quotations. "
            f"File: {config.CORPUS_PATH.name}"
        )

    st.divider()
    rows = log.rows()
    with st.expander(f"Session log: {len(rows)} row(s)"):
        st.caption(
            "One row per question: retrieved ids, scores, refusal, latency, "
            "removed citations. Used as development evidence."
        )
        st.download_button(
            "Download CSV",
            data=log.path.read_bytes() if log.path.exists() else b"",
            file_name=log.path.name,
            mime="text/csv",
            width="stretch",
        )
    if st.button("Clear conversation", width="stretch"):
        st.session_state["history"] = []
        st.rerun()

# --- main --------------------------------------------------------------------
st.title("LitLens")
st.caption(
    "Ask about filter bubbles, recommender explanations and interaction design. "
    "Answers use only the corpus passages, cite them as [S1], and are refused "
    "when the corpus cannot support them."
)

with st.expander("How an answer is produced", expanded=not st.session_state["history"]):
    st.markdown(
        "1. **Retrieve** — TF-IDF search over 17 paraphrase notes; top 3, "
        "English and Chinese indexed together.\n"
        "2. **Refuse or continue** — if the best score is below "
        f"`MIN_SCORE = {config.MIN_SCORE:.2f}`, stop before calling the model.\n"
        "3. **Generate** — DeepSeek `deepseek-flash`, thinking mode off, "
        "instructed to use only the numbered passages.\n"
        "4. **Verify** — any `[Sn]` that is not a retrieved passage is removed "
        "and reported; the evidence stays visible beside the answer."
    )

for turn in st.session_state["history"]:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        render_body(turn, st.empty())

if not st.session_state["history"]:
    st.markdown("**Try one:**")
    cols = st.columns(len(EXAMPLES))
    for col, example in zip(cols, EXAMPLES):
        with col:
            if st.button(example, width="stretch"):
                run_turn(example, evidence_only, log)
                st.rerun()

if question := st.chat_input("Ask a question (English or Chinese)…"):
    run_turn(question, evidence_only, log)
    st.rerun()

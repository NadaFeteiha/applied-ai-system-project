import json
import streamlit as st
from pathlib import Path

# ── Shared data (kept alive via session_state across pages) ───────────────────
DATA_FILE = Path("pawpal_data.json")


def _init_db():
    if "db" not in st.session_state:
        st.session_state.db = (
            json.loads(DATA_FILE.read_text())
            if DATA_FILE.exists()
            else {"owners": {}}
        )


_init_db()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"] { font-family: 'Inter', sans-serif; }
[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(160deg, #0d1117 0%, #161b27 40%, #1a1f35 100%);
    min-height: 100vh;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stSidebar"] { background: #161b27 !important; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a1f35; }
::-webkit-scrollbar-thumb { background: #667eea; border-radius: 3px; }

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(102,126,234,0.3); }
    50%       { box-shadow: 0 0 44px rgba(102,126,234,0.6); }
}

/* ── Hero ── */
.ai-hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 48%, #f64f59 100%);
    border-radius: 24px; padding: 44px 40px; text-align: center;
    margin-bottom: 28px;
    box-shadow: 0 24px 64px rgba(102,126,234,0.35);
    animation: fadeInUp 0.65s ease-out, pulse-glow 4s ease-in-out infinite;
}
.ai-hero h1 {
    color: white; font-size: 2.6em; margin: 0;
    font-weight: 800; letter-spacing: -1px;
    text-shadow: 0 2px 20px rgba(0,0,0,0.25);
}
.ai-hero p { color: rgba(255,255,255,0.85); font-size: 1.05em; margin: 10px 0 0; }

/* ── Status badges ── */
.ai-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 12px; border-radius: 20px;
    font-size: 0.76em; font-weight: 600; margin-right: 6px;
}
.ai-badge-online  { background: rgba(52,211,153,0.12);  border: 1px solid rgba(52,211,153,0.35);  color: #34d399; }
.ai-badge-offline { background: rgba(239,68,68,0.1);    border: 1px solid rgba(239,68,68,0.35);   color: #f87171; }
.ai-badge-docs    { background: rgba(165,180,252,0.1);  border: 1px solid rgba(165,180,252,0.3);  color: #a5b4fc; }

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(102,126,234,0.1), rgba(118,75,162,0.07)) !important;
    border: 1px solid rgba(102,126,234,0.2) !important;
    border-radius: 14px !important; padding: 16px !important;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; }
[data-testid="stMetricLabel"] { color: #6b7280 !important; }

/* ── Chat bubbles ── */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 16px !important;
    margin-bottom: 8px !important;
}

/* ── Source pills ── */
.src-pills-row {
    display: flex; flex-wrap: wrap; gap: 6px;
    margin-top: 10px; padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.07);
}
.src-pill {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 11px; border-radius: 20px; font-size: 0.74em; font-weight: 600;
}
.src-pill-care   { background: rgba(102,126,234,0.12); border: 1px solid rgba(102,126,234,0.3); color: #818cf8; }
.src-pill-dr     { background: rgba(251,191,36,0.10);  border: 1px solid rgba(251,191,36,0.3);  color: #fbbf24; }
.src-pill-custom { background: rgba(52,211,153,0.10);  border: 1px solid rgba(52,211,153,0.30); color: #34d399; }

.confidence-bar-wrap {
    display: flex; align-items: center; gap: 8px;
    margin-top: 8px; padding-top: 8px;
    border-top: 1px solid rgba(255,255,255,0.07);
}
.confidence-label { color: #6b7280; font-size: 0.74em; white-space: nowrap; }
.confidence-bar {
    flex: 1; height: 4px; border-radius: 2px;
    background: rgba(255,255,255,0.08);
    overflow: hidden;
}
.confidence-fill { height: 100%; border-radius: 2px; }
.confidence-pct  { color: #9ca3af; font-size: 0.74em; white-space: nowrap; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 10px !important; font-weight: 600 !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(102,126,234,0.3) !important;
}

hr { border-color: rgba(102,126,234,0.18) !important; }

[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(102,126,234,0.2) !important;
    border-radius: 14px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── RAG imports ───────────────────────────────────────────────────────────────
try:
    from rag import ask as rag_ask, is_index_populated
    from rag import ingest_bytes, remove_source, list_sources, run_eval_suite
    from rag.llm import is_available as _llm_available
    from rag.vector_store import count as _kb_count
    from rag.evaluator import avg_similarity_score

    _rag_ok = True
except ImportError:
    _rag_ok = False

# ── Sidebar — owner context ───────────────────────────────────────────────────
owner_names = list(st.session_state.db.get("owners", {}).keys())

with st.sidebar:
    if st.button("← Back to PawPal+", use_container_width=True):
        st.switch_page("pages/Home.py")
    st.markdown(
        '<div style="color:#a5b4fc;font-weight:700;font-size:0.8em;'
        'letter-spacing:0.08em;margin-bottom:10px">👤 OWNER CONTEXT</div>',
        unsafe_allow_html=True,
    )
    if owner_names:
        selected_owner = st.selectbox(
            "Select owner",
            owner_names,
            key="ai_owner_select",
            label_visibility="collapsed",
        )
        o_data = st.session_state.db["owners"].get(selected_owner, {})
        pets = o_data.get("pets", [])
        st.markdown(
            f'<div style="color:#6b7280;font-size:0.82em;margin-top:6px">'
            f'{len(pets)} pet{"s" if len(pets) != 1 else ""} linked</div>',
            unsafe_allow_html=True,
        )
        for p in pets:
            st.markdown(
                f'<div style="color:#e8eaf6;font-size:0.85em;padding:4px 0">'
                f'{"🐶" if p["species"]=="dog" else "🐱" if p["species"]=="cat" else "🐦" if p["species"]=="bird" else "🐰" if p["species"]=="rabbit" else "🐟"}'
                f' {p["name"]}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No owners yet — add one on the main page first.")
        selected_owner = None

    st.divider()
    st.markdown(
        '<div style="color:#a5b4fc;font-weight:700;font-size:0.8em;'
        'letter-spacing:0.08em;margin-bottom:10px">📚 KNOWLEDGE BASE</div>',
        unsafe_allow_html=True,
    )
    if _rag_ok:
        _llm_on = _llm_available()
        _doc_count = _kb_count()
        st.markdown(
            f'<span class="ai-badge ai-badge-{"online" if _llm_on else "offline"}">'
            f'● Ollama {"online" if _llm_on else "offline"}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<span class="ai-badge ai-badge-docs" style="margin-top:6px;display:inline-flex">'
            f'📚 {_doc_count} chunks</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="color:#6b7280;font-size:0.78em;margin-top:10px;line-height:1.5">'
            '6 vet doctor profiles<br>5 pet care guides<br>Dogs · Cats · Birds · Rabbits · Fish'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("RAG not installed")

    if _rag_ok:
        st.divider()
        st.markdown(
            '<div style="color:#a5b4fc;font-weight:700;font-size:0.8em;'
            'letter-spacing:0.08em;margin-bottom:10px">📎 CUSTOM DOCUMENTS</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="color:#6b7280;font-size:0.78em;margin-bottom:10px;line-height:1.5">'
            'Upload .txt or .pdf files to extend the knowledge base. '
            'Custom documents are retrieved alongside built-in guides.</div>',
            unsafe_allow_html=True,
        )

        if "custom_indexed" not in st.session_state:
            st.session_state.custom_indexed = set()

        uploaded = st.file_uploader(
            "Upload document",
            type=["txt", "pdf"],
            key="custom_doc_uploader",
            label_visibility="collapsed",
        )
        if uploaded and uploaded.name not in st.session_state.custom_indexed:
            with st.spinner(f"Indexing {uploaded.name}…"):
                try:
                    n = ingest_bytes(
                        uploaded.read(),
                        filename=uploaded.name,
                    )
                    st.session_state.custom_indexed.add(uploaded.name)
                    st.success(f"Indexed {n} chunks from {uploaded.name}")
                except Exception as exc:
                    st.error(f"Failed to index: {exc}")

        custom_sources = [
            s for s in list_sources() if s.get("source_type") == "custom"
        ]
        if custom_sources:
            st.markdown(
                '<div style="color:#6b7280;font-size:0.78em;margin-bottom:6px">'
                'Indexed custom sources:</div>',
                unsafe_allow_html=True,
            )
            for src in custom_sources:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(
                        f'<div style="color:#34d399;font-size:0.82em;padding:3px 0">'
                        f'📄 {src["source"]}'
                        f'<span style="color:#6b7280"> · {src["count"]} chunks</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("✕", key=f"del_{src['source']}", help="Remove source"):
                        remove_source(src["source"])
                        st.session_state.custom_indexed.discard(
                            src["source"].lower().replace(" ", "_") + ".txt"
                        )
                        st.rerun()
        else:
            st.markdown(
                '<div style="color:#4b5563;font-size:0.78em;font-style:italic">'
                'No custom documents yet.</div>',
                unsafe_allow_html=True,
            )

# ── Hero banner ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="ai-hero">
        <h1>🤖 PawPal AI Assistant</h1>
        <p>Ask anything about pet care or vet appointments — grounded in a curated knowledge base.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Metrics row ───────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Vet Doctors", "6", delta="profiles loaded")
with m2:
    st.metric("Pet Guides", "5", delta="species covered")
with m3:
    st.metric("Knowledge Chunks", str(_doc_count if _rag_ok else 0), delta="indexed")
with m4:
    st.metric("LLM Engine", "llama3.2", delta="via Ollama")

st.divider()

# ── Retrieval quality panel ───────────────────────────────────────────────────
if _rag_ok:
    with st.expander("🔎 Retrieval Quality Evaluation", expanded=False):
        st.markdown(
            "Run the built-in evaluation suite to measure how well the knowledge base "
            "retrieves relevant content. **Keyword coverage** checks whether expected "
            "terms appear in the top-5 chunks. **Similarity score** is the mean cosine "
            "similarity of those chunks to the query."
        )

        _cat_counts = {}
        try:
            from rag.vector_store import count_by_category as _count_by_cat
            _cat_counts = _count_by_cat()
        except Exception:
            pass

        if _cat_counts:
            _cc1, _cc2, _cc3 = st.columns(3)
            _cc1.metric("pet_care chunks",  _cat_counts.get("pet_care", 0))
            _cc2.metric("doctors chunks",   _cat_counts.get("doctors", 0))
            _cc3.metric("custom chunks",    _cat_counts.get("custom", 0))

        if st.button("▶ Run Evaluation Suite (8 questions)", key="run_eval"):
            with st.spinner("Evaluating retrieval across 8 reference questions…"):
                _eval = run_eval_suite()

            _e1, _e2 = st.columns(2)
            _e1.metric(
                "Avg Keyword Coverage",
                f"{_eval['avg_keyword_coverage']:.0%}",
                help="Fraction of expected topic keywords found in retrieved chunks",
            )
            _e2.metric(
                "Avg Similarity Score",
                f"{_eval['avg_similarity_score']:.0%}",
                help="Mean cosine similarity between query and retrieved chunks",
            )

            st.markdown("**Per-question results:**")
            for _r in _eval["per_question"]:
                _cov = _r["keyword_coverage"]
                _sim = _r["avg_similarity"]
                _cov_color = "🟢" if _cov >= 0.7 else "🟡" if _cov >= 0.4 else "🔴"
                _sources_str = ", ".join(_r["sources"]) if _r["sources"] else "—"
                st.markdown(
                    f"**{_r['question']}**  \n"
                    f"{_cov_color} Coverage: `{_cov:.0%}` &nbsp;|&nbsp; "
                    f"Similarity: `{_sim:.0%}` &nbsp;|&nbsp; "
                    f"Sources: *{_sources_str}*"
                )

st.divider()

# ── Guard: RAG not ready ──────────────────────────────────────────────────────
if not _rag_ok:
    st.error(
        "RAG dependencies are not installed. Run these commands, then refresh:\n\n"
        "```\npip install sentence-transformers chromadb\npython setup_rag.py\n```"
    )
    st.stop()

if not is_index_populated():
    st.info("Knowledge base not indexed yet. Run the command below once, then refresh the app.")
    st.code("python setup_rag.py", language="bash")
    st.stop()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_due(frequency: str) -> str:
    from datetime import date, timedelta
    today = date.today()
    if frequency == "daily":
        return today.strftime("%A, %B %d")
    if frequency == "weekly":
        days_until_monday = (7 - today.weekday()) % 7 or 7
        return (today + timedelta(days=days_until_monday)).strftime("%A, %B %d")
    if frequency == "monthly":
        if today.month == 12:
            first = date(today.year + 1, 1, 1)
        else:
            first = date(today.year, today.month + 1, 1)
        return first.strftime("%A, %B %d")
    return "unknown"


def _user_context(owner_name: str | None) -> str:
    if not owner_name:
        return ""
    o = st.session_state.db["owners"].get(owner_name, {})
    lines = [f"Owner: {owner_name}"]
    for p in o.get("pets", []):
        lines.append(f"Pet: {p['name']} ({p['species']}, age {p['age']})")
        for t in p.get("tasks", []):
            freq = t.get("frequency", "")
            times = t.get("times_per_day", 1)
            dur = t.get("duration", "")
            next_due = _next_due(freq)
            detail = f"{freq}, next due: {next_due}"
            if times > 1:
                detail += f", {times}x/day"
            if dur:
                detail += f", {dur} min"
            lines.append(f"  - Task: {t['name']} ({detail})")
    return "\n".join(lines)


def _source_pills(sources: list) -> str:
    seen, pills = set(), []
    for src in sources:
        meta = src["metadata"]
        name = meta.get("source", "unknown")
        cat = meta.get("category", "")
        src_type = meta.get("source_type", "builtin")
        if name in seen:
            continue
        seen.add(name)
        if cat == "doctors":
            cls, icon = "src-pill-dr", "🩺"
        elif src_type == "custom":
            cls, icon = "src-pill-custom", "📎"
        else:
            cls, icon = "src-pill-care", "📖"
        pills.append(f'<span class="src-pill {cls}">{icon} {name}</span>')
    return f'<div class="src-pills-row">{"".join(pills)}</div>' if pills else ""


def _confidence_bar(sources: list) -> str:
    if not sources:
        return ""
    score = avg_similarity_score(sources)
    pct = int(score * 100)
    color = "#34d399" if score >= 0.70 else "#fbbf24" if score >= 0.50 else "#f87171"
    return (
        '<div class="confidence-bar-wrap">'
        '<span class="confidence-label">Retrieval confidence</span>'
        '<div class="confidence-bar">'
        f'<div class="confidence-fill" style="width:{pct}%;background:{color}"></div>'
        '</div>'
        f'<span class="confidence-pct">{pct}%</span>'
        '</div>'
    )


# ── Quick-question pills ──────────────────────────────────────────────────────
_examples = [
    "Which doctor for my rabbit?",
    "Dr. Chen — Saturday hours?",
    "How to book Dr. Wilson?",
    "How often to walk my dog?",
    "Foods toxic to cats?",
    "Bird specialist contact?",
    "What vaccines does my dog need?",
    "Is Dr. Thompson available on Sundays?",
    "Emergency vet — who to call?",
]

st.markdown(
    '<p style="color:#6b7280;font-size:0.8em;font-weight:500;'
    'letter-spacing:0.05em;margin:0 0 8px 0">💡 QUICK QUESTIONS — click any to ask instantly</p>',
    unsafe_allow_html=True,
)

if "rag_pill_submitted" not in st.session_state:
    st.session_state.rag_pill_submitted = None

_selected_pill = st.pills(
    "Quick questions",
    options=_examples,
    selection_mode="single",
    key="rag_pill_select",
    label_visibility="collapsed",
)
if _selected_pill and _selected_pill != st.session_state.rag_pill_submitted:
    st.session_state.rag_pill_submitted = _selected_pill
    st.session_state["_pending_question"] = _selected_pill

st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

# ── Chat history & clear button ───────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if st.session_state.chat_history:
    _, _btn_col = st.columns([9, 1])
    with _btn_col:
        if st.button("🗑 Clear", key="clear_chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.rag_pill_submitted = None
            st.rerun()

# ── Render existing messages ──────────────────────────────────────────────────
for _msg in st.session_state.chat_history:
    with st.chat_message(_msg["role"]):
        st.markdown(_msg["content"])
        if _msg["role"] == "assistant" and _msg.get("sources"):
            st.markdown(_source_pills(_msg["sources"]), unsafe_allow_html=True)
            st.markdown(_confidence_bar(_msg["sources"]), unsafe_allow_html=True)

# ── Handle new question ───────────────────────────────────────────────────────
_pending = st.session_state.pop("_pending_question", None)
_typed = st.chat_input("Ask about pet care or vet appointments…")
_question = _pending or _typed

if _question:
    st.session_state.chat_history.append({"role": "user", "content": _question})
    with st.chat_message("user"):
        st.markdown(_question)

    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge base…"):
            _ctx = _user_context(selected_owner)
            _result = rag_ask(_question, user_context=_ctx)
        st.markdown(_result["answer"])
        if not _result["llm_used"]:
            st.caption("⚠️ Ollama is offline — showing retrieved knowledge base excerpts.")
        if _result.get("sources"):
            st.markdown(_source_pills(_result["sources"]), unsafe_allow_html=True)
            st.markdown(_confidence_bar(_result["sources"]), unsafe_allow_html=True)

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": _result["answer"],
        "sources": _result.get("sources", []),
    })

# PawPal+

> AI-powered pet care scheduling with a local RAG pipeline — no cloud API key required.

PawPal+ was built for pet owners who struggle to stay consistent with care routines. It combines a structured 7-day scheduling engine with an embedded AI assistant that can answer pet care questions and surface vet availability — all running locally on your machine. The goal was to make AI genuinely useful in a domain-specific context, not just a chatbot bolted on top.

**[Watch the demo on Loom →](https://www.loom.com/share/35a6355b87ad45e98db4f5789fa0803a)**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Setup Instructions](#setup-instructions)
3. [Sample Interactions](#sample-interactions)
4. [Design Decisions](#design-decisions)
5. [Testing Summary](#testing-summary)
6. [Reflection](#reflection)

---

## Architecture Overview

The system is split into two parallel pipelines that share the same UI shell:

```mermaid
flowchart TD
    USER(["👤 Pet Owner"])

    USER -->|"pet care question"| Q_INPUT["Question Input"]
    USER -->|"pets · tasks · availability"| S_INPUT["Schedule Input"]

    subgraph RETRIEVER["🔍 Retriever"]
        direction TB
        KB["Knowledge Base\n11 documents\npet care · vet profiles"]
        EMB["Embedder\nall-MiniLM-L6-v2\n384-dim vectors"]
        VDB[("ChromaDB\nVector Store\ncosine similarity")]
        KB -->|"setup_rag.py — one-time index"| VDB
        EMB -->|"query vector"| VDB
    end

    subgraph AGENT["🧠 Agent / LLM"]
        direction TB
        PROMPT["Prompt Builder\n+ owner & pet context"]
        LLM["Ollama llama3.2\nlocal inference"]
        FALLBACK["Fallback Mode\nraw KB excerpts"]
        PROMPT --> LLM
        PROMPT -->|"Ollama offline"| FALLBACK
    end

    subgraph SCHEDULER["⚙️ Scheduling Engine"]
        direction TB
        SCHED["Scheduler\n7-day plan · recurrence · calendar"]
        SLOTS["Slot Builder\nfree-block placement · busy-window enforcement"]
        SCHED --> SLOTS
    end

    subgraph EVALUATOR["🔎 Evaluator"]
        direction TB
        CONFLICT["Conflict Detector\nO(n²) pairwise overlap scan"]
        SEVERITY["Severity Classifier\nMinor · Moderate · Major"]
        SUGGEST["Auto-Fix Suggester\npriority-aware recommendation"]
        CONFLICT --> SEVERITY --> SUGGEST
    end

    subgraph TESTER["🧪 Test Suite"]
        PYTEST["pytest · 131 tests\n100% backend coverage\n42 edge & boundary cases"]
    end

    Q_INPUT --> EMB
    VDB -->|"Top-5 chunks"| PROMPT
    LLM -->|"grounded answer"| AI_OUT["💬 AI Answer + source pills"]
    FALLBACK -->|"excerpts + warning badge"| AI_OUT

    S_INPUT --> SCHED
    SLOTS --> CONFLICT

    AI_OUT --> HUMAN["👤 Human Review"]
    SUGGEST --> HUMAN
    HUMAN -->|"source verification\n— trust signal from RAG"| AI_OUT
    HUMAN -->|"accept auto-fix or\nmanual override"| SLOTS

    TESTER -.->|"validates"| SCHEDULER
    TESTER -.->|"validates"| EVALUATOR
```

### How it fits together

**RAG pipeline (left branch):** The user types a question. The embedder converts it to a 384-dimensional vector and queries ChromaDB for the top-5 most semantically similar chunks from the knowledge base. Those chunks, along with the owner's pet context, are assembled into a prompt that is sent to a local Ollama LLM. If Ollama is not running, the system falls back to surfacing the raw retrieved excerpts with a warning badge — the answer degrades gracefully rather than failing.

**Scheduling pipeline (right branch):** The owner's pets and tasks feed into the scheduler, which builds a 7-day plan filtered by recurrence rules and calendar availability. The slot builder places each task inside the owner's free time blocks, respecting busy windows. The conflict detector then scans every pair of placed tasks for time overlap and classifies the severity. When a conflict is found, the evaluator suggests a priority-aware fix and the owner applies it — or overrides it manually.

**Human-in-the-loop:** Both pipelines keep the owner in control. For AI answers, source pills show exactly which knowledge base document was used so the answer can be verified. For scheduling, auto-fix suggestions require explicit acceptance and every task duration can be overridden by hand.

**Test suite:** 131 automated tests validate the scheduling engine and evaluator independently of the UI. The dashed lines in the diagram represent this offline validation layer.

---

## Setup Instructions

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com) (for full LLM responses — optional, the app runs without it)

### Install

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

### Index the knowledge base (one-time)

```bash
python setup_rag.py
```

Expected output:

```
dogs.txt        →  18 chunks
cats.txt        →  15 chunks
birds.txt       →  12 chunks
rabbits.txt     →  11 chunks
fish.txt        →   9 chunks
dr_sarah_chen.txt       →  6 chunks
dr_james_wilson.txt     →  6 chunks
dr_emily_rodriguez.txt  →  6 chunks
dr_michael_patel.txt    →  6 chunks
dr_lisa_thompson.txt    →  6 chunks
dr_omar_hassan.txt      →  6 chunks

Total chunks indexed: 301
Done! ChromaDB is ready.
```

### Set up Ollama (for full AI answers)

```bash
# Install from https://ollama.com, then:
ollama pull llama3.2
```

The sidebar in the app shows a live `● Ollama online / offline` badge so you always know which mode is active.

### Run the app

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501`. Click **Open Chat →** on the home page to reach the AI assistant.

---

## Sample Interactions

The examples below show real queries and the kind of answers the system returns when Ollama is online. Each answer is grounded in the indexed knowledge base — the source pills shown in the UI tell you which document backed the response.

---

### Example 1 — Vet availability

**User question:**
> Is Dr. Sarah Chen available on weekends, and what does a consultation cost?

**AI answer:**
> Dr. Sarah Chen is available Monday through Saturday, 9:00 AM to 5:00 PM. She does not see patients on Sundays. A standard consultation is $85. She specialises in small animals and exotic pets. To book an appointment, call her clinic directly or use the online booking link in her profile.

**Sources:** `🩺 dr_sarah_chen`

---

### Example 2 — Species-specific care

**User question:**
> How often should I feed my rabbit, and are there foods I should avoid?

**AI answer:**
> Rabbits should have unlimited timothy hay available at all times — it should make up about 80% of their diet. Fresh leafy greens (romaine lettuce, cilantro, parsley) can be given daily in small amounts, roughly one cup per two pounds of body weight. Fresh water must always be available.
>
> Foods to avoid: iceberg lettuce, sugary fruits in large quantities, onions, garlic, avocado, and any processed human food. Pellets should be limited to about a tablespoon per day for adult rabbits to prevent obesity.

**Sources:** `📖 rabbits`

---

### Example 3 — Emergency referral with pet context

**User question (with owner context: Max the dog, age 3):**
> My dog ate something he shouldn't have — which vet should I contact first?

**AI answer:**
> For urgent or emergency cases, Dr. James Wilson handles emergency consultations and is reachable outside normal hours. His clinic number is listed in his profile. Dr. Michael Patel also sees dogs and has availability earlier in the week if the situation is not immediately critical.
>
> In the meantime, keep Max calm, note what he ate and when, and bring that information when you call. Do not induce vomiting unless a vet specifically instructs you to.

**Sources:** `🩺 dr_james_wilson` `🩺 dr_michael_patel` `📖 dogs`

---

## Design Decisions

### Why a local RAG pipeline instead of a cloud LLM API?

The goal was a system that works offline and keeps all pet owner data on the user's machine. A cloud API would require an API key, incur per-request costs, and send potentially sensitive owner and pet data to an external server. Using Ollama with a local model eliminates all three concerns. The trade-off is that local inference is slower and the model is smaller, but for a domain-specific assistant grounded in a curated knowledge base, answer quality is acceptable.

### Why ChromaDB for vector storage?

ChromaDB persists the index to disk automatically (`chroma_db/` directory), which means the knowledge base only needs to be indexed once via `setup_rag.py`. It has a simple Python API and handles cosine similarity search without needing a separate database server. The trade-off is that it is not designed for large-scale production workloads — for a pet care scheduling app with a few hundred chunks, it is the right fit.

### Why `all-MiniLM-L6-v2` for embeddings?

It is small (80 MB), fast, and produces high-quality 384-dimensional semantic vectors for English text. Larger embedding models would improve retrieval precision marginally but would significantly slow down first-load time. For a knowledge base of ~300 chunks, the retrieval quality with `all-MiniLM-L6-v2` is strong enough that the bottleneck is the LLM, not the retriever.

### Why 200-word chunks with 30-word overlap?

Pet care guides and vet profiles contain dense, self-contained paragraphs. A 200-word chunk is large enough to hold a coherent piece of advice (e.g., a full feeding guideline or a vet's availability block) without splitting it mid-thought. The 30-word overlap ensures that sentences at chunk boundaries appear in at least two chunks, so a query that maps to a boundary is still retrievable.

### Why keep scheduling and AI as separate pipelines?

Scheduling is deterministic — the same inputs always produce the same plan. The AI assistant is probabilistic. Mixing them would make the system harder to test, harder to debug, and harder to explain. Keeping them separate means the scheduler can reach 100% test coverage while the AI assistant is evaluated through the human-in-the-loop interaction pattern (source verification, manual override).

### Priority vs. preference trade-off in scheduling

The scheduler enforces a hard `high → medium → low` priority order within each day. If an owner prefers to walk their dog in the evening but feeding (a high-priority task) overlaps, feeding wins and the walk is adjusted. This is a deliberate trade-off: pet health tasks must be non-negotiable, but owner comfort is preserved wherever it does not conflict with a higher-priority task. The conflict detection layer then makes any remaining overlaps visible and actionable.

---

## Testing Summary

### What was tested

The test suite covers two reliability layers: the deterministic scheduling backend (automated unit tests) and the probabilistic RAG pipeline (confidence scoring + evaluator unit tests).

```
164 passed, 1 warning in 8.87s
```

**Scheduling backend** — 131 tests, 100% statement coverage on `pawpal_system.py`

| Category | Tests | Focus |
|---|:---:|---|
| Data Models & Core Objects | 27 | Construction, relationships, bidirectional linking |
| Task Management & Lifecycle | 22 | Add / remove / edit, completion, `active_from` gate |
| Scheduling Engine | 22 | 7-day window, recurrence, priority ordering |
| Conflict Detection | 24 | Overlap geometry, severity boundaries |
| Time-Aware Scheduling | 36 | Free-block placement, busy-window enforcement, multi-occurrence spread |

**RAG evaluator** — 33 tests across two categories

| Category | Tests | Focus |
|---|:---:|---|
| `keyword_coverage` (unit) | 12 | All/none/partial match, case-insensitivity, empty inputs, substring matching |
| `avg_similarity_score` (unit) | 9 | Single/multi-chunk averages, boundary scores (0, 1), rounding |
| `evaluate_question` (integration) | 6 | Return shape, value ranges, question passthrough — requires indexed KB |
| `run_eval_suite` (integration) | 6 | Suite completeness, aggregate range checks, minimum quality floor |

Integration tests auto-skip when ChromaDB has not been indexed yet (they print a clear "run `python setup_rag.py` first" message).

42 of the 131 scheduling tests explicitly target edge and boundary conditions. The 12 evaluator unit tests do the same for the scoring functions — zero chunks, zero keywords, exact boundary scores, case folding.

### Confidence scoring in the UI

Every AI response shows a **retrieval confidence bar** — the mean cosine-similarity of the top-5 retrieved chunks displayed as a percentage with a color-coded fill (green ≥ 70%, yellow 50–69%, red < 50%). The **Retrieval Quality Evaluation** panel in the app runs the full 8-question reference suite on demand and reports aggregate keyword coverage and similarity scores.

### Why scores sit in the 50–60% range

Scores in the yellow zone are expected and do not mean the answer is wrong. Two metrics measure different things:

- **Similarity score** — how geometrically close the query vector is to the retrieved chunk vectors
- **Keyword coverage** — whether the right content was actually retrieved

A short question (8–12 words) compared against a 200-word chunk will always produce a diluted similarity score, because the chunk contains many words unrelated to the specific question and the two vectors cannot point in exactly the same direction. The evaluation suite confirms this: all 8 reference questions scored 44–57% similarity while achieving 97% keyword coverage — the right content was retrieved every time, just at moderate similarity.

| Factor | Effect on score |
|---|---|
| Short query vs. long chunk | Query vector is specific; chunk vector is diffuse — close alignment is impossible |
| General-purpose embedding model | `all-MiniLM-L6-v2` was not trained on pet care vocabulary |
| 200-word chunks | More off-topic words per chunk lowers similarity to any single question |

**To push scores into the green zone** the most effective change is reducing chunk size (e.g., 80 words instead of 200) in [rag/ingest.py](rag/ingest.py). Smaller chunks have less off-topic content so similarity typically rises to 70–85%. The trade-off is that very small chunks may split a useful fact across two chunks and hurt keyword coverage.

### Results summary

All 164 automated tests passed. The 8-question RAG evaluation showed strong keyword coverage (97% average) — the retriever consistently pulled the right content — while semantic similarity averaged 50%, landing in the "yellow" zone, meaning chunks are topically correct but not always a tight match for the phrasing of the question. The weakest result was the fish care query, which missed one of five expected keywords (80% coverage vs 100% for every other question). No query fell below the 50% similarity floor; adding a species-specific document (e.g., a breed guide) raises confidence scores into the green zone, as shown in the custom document example above.

### What worked well

Testing the scheduling engine against explicit boundary values (e.g., conflict severity at exactly 5, 6, and 15 minutes) caught a subtle off-by-one in the severity classifier early. The `active_from` deferred scheduling logic was also validated precisely — a task is hidden before its activation date and visible on it, not one day after — and that boundary would have been easy to get wrong without a dedicated test.

### What did not get covered

The Streamlit UI layer (`app.py`, `pages/`) is not covered by automated tests. The LLM generation step is also excluded — testing it would require a live Ollama instance or a mocked model, and the fallback behavior (raw chunk excerpts when Ollama is offline) was verified manually. A future iteration would add snapshot tests for the rendered schedule and end-to-end tests that exercise the full generate-then-evaluate loop.

### What the process revealed

Writing tests before fully implementing some features (especially the `active_from` logic) forced cleaner method contracts. The test failures were more informative than runtime errors would have been. It also made refactoring safer — after changing how the tracker stores completion logs, the test suite immediately surfaced the two downstream functions that needed updating.

---

## Reflection

### What building a RAG system taught me

RAG is deceptively simple to set up and surprisingly hard to tune. Getting the pipeline running took a few hours. Getting it to return *actually useful* answers required careful decisions about chunk size, overlap, and prompt structure. The biggest lesson was that retrieval quality and generation quality are separate problems — a well-written prompt cannot compensate for chunks that are too large, too small, or split at the wrong boundaries.

The fallback mode (returning raw chunks when Ollama is offline) was originally an afterthought, but it turned out to be one of the most useful features. It made the system testable without Ollama running and gave users a transparent view of what the LLM was actually working from.

### What building a tested system taught me

100% line coverage does not mean the system is correct — it means every line was executed at least once. The more valuable metric was the 42 edge case tests, which tested *intent* rather than just execution. A line that always runs is not the same as a line that behaves correctly at its boundaries.

Testing also changed how I wrote the code. Knowing a function would need a test made me think harder about its interface before writing the body. Functions that were hard to test were usually functions that were trying to do too much.

### What the human-in-the-loop design taught me

The AI assistant is only trustworthy because the source pills are always shown. Without them, the owner has no way to know whether an answer came from a real vet profile or was hallucinated. Showing sources is not just a nice feature — it is what makes the system safe to act on. This applies beyond this project: any AI system that produces advice people might act on needs a transparency mechanism, even a simple one.

The conflict auto-fix follows the same principle. The system makes a recommendation, explains its reasoning (the lower-priority task is identified by name), and requires the owner to click a button to apply it. A single-step auto-apply without review would be faster, but it would also remove the owner from the loop at exactly the moment a mistake could go unnoticed.

### One key takeaway

Start with the simplest design that could possibly work, test it thoroughly, and only then add complexity. The scheduling engine started as a flat list of tasks sorted by priority. Conflict detection, time-aware placement, and multi-occurrence spreading were each added one at a time, with tests written for each layer before the next was built. That incremental approach kept the system understandable at every stage and made each new feature easier to reason about.

---

## Critical Reflection

### Limitations and biases

The knowledge base is hand-curated and small — 11 documents covering five species and six vets. Any pet not in that set (reptiles, guinea pigs, senior dogs with chronic conditions) will get a generic or irrelevant answer, and the system currently has no way to signal that a question is outside its coverage. The vet profiles are also fictional, so availability and fee data is static and never goes stale, but it also means the booking information cannot be acted on.

A second structural limitation showed up during testing: the original prompt gave the LLM no instruction about which source of truth to trust when they conflicted. When a user asked "which doctor for my rabbit?" while having a dog registered in the system, the AI ignored the registered pet data and recommended a rabbit specialist — confidently and incorrectly. The fix was a single instruction added to the prompt telling the model to treat owner data as ground truth and flag any mismatch. This is a limitation of instruction-following LLMs in general: without explicit priority rules, they resolve ambiguity based on the question wording, not the data.

On the bias side, the retriever uses cosine similarity on short queries, which favors questions phrased similarly to the training documents. A user who asks "my cat keeps throwing up" may get lower-confidence results than one who asks "what causes vomiting in cats," even though the intent is the same. The scoring also weights semantic closeness, not medical correctness — a confident-looking 80% score does not mean the answer is safe to act on without a real vet.

### Misuse risks and safeguards

The most realistic misuse is over-reliance: an owner treating an AI answer as a substitute for professional veterinary advice. A second risk is prompt injection through custom documents — a malicious upload could embed instructions designed to hijack the LLM's response.

Safeguards already in place: source pills on every answer make it clear where information came from; the fallback mode shows raw chunks rather than a confident-sounding generated sentence when the LLM is offline; and the custom document upload is type-restricted to `.txt` and `.pdf`. What is not yet in place: a disclaimer on health-related answers, rate limiting on document uploads, and sanitization of uploaded text before it enters the prompt.

### What surprised me during reliability testing

The keyword coverage metric (97% average) looked excellent, but the similarity scores (50% average) told a different story — the retriever was finding the right documents but not always the most on-point passages within them. I expected those two numbers to move together. The surprise was that coverage can be high while similarity is only moderate: the keyword is present somewhere in the top-5 chunks, but the chunk that contains it may have been retrieved for a different reason. That gap is what a re-ranking step would fix, and I would not have noticed it without running both metrics side by side.

The fish care question was the only one to miss a keyword (80% coverage). Looking at the retrieved chunks, the word "aquarium" was present but "filter" was not — the knowledge base document uses "filtration system" instead. That single synonym mismatch was enough to drop the score, which is a good reminder that keyword matching punishes vocabulary gaps even when the underlying information is there.

Two failures during live testing were more surprising than anything the automated suite caught. First, asking "when is Oreo's appointment?" returned a response asking the user to confirm the date — even though the appointment was in the database. The cause was that `_user_context()` was only passing task names (`"appointment"`) with no details, so the AI had nothing to work from. The fix was to include frequency, duration, and a computed next-due date in the context string. Second, asking "which doctor for my rabbit?" while Oreo was registered as a dog caused the AI to recommend a rabbit specialist — it followed the question wording and completely ignored the registered species. Both failures passed all 164 automated tests, which only validated the scheduling engine and scoring functions. They were only caught through manual use, reinforcing that automated tests and live testing catch different classes of bugs.

### Collaboration with AI during this project

AI assistance was used throughout — for scaffolding the RAG pipeline, writing the test suite, fixing bugs, and drafting documentation.

**Helpful instance:** When the species mismatch bug appeared (the AI recommending a rabbit doctor for Oreo the dog), the fix suggested was to add a single priority instruction to the prompt: *"If the user's pet data is provided, treat it as ground truth and flag any mismatch with the question."* That one-line prompt change resolved the issue without touching any retrieval logic. It was a good example of the AI identifying that the problem was in the instruction layer, not the data layer — a distinction that would have taken longer to reach independently.

**Flawed instance:** The AI initially proposed testing `keyword_coverage` with the assertion that `"vaccine"` would be found as a substring of `"vaccination"`. The test was written and only caught when it failed at runtime — `"vaccine"` and `"vaccination"` diverge at the seventh character and are not a substring match. A second flawed suggestion was that the `_user_context()` function was already passing enough information for the AI to answer appointment questions. In practice it was only passing task names (`"appointment"`) with no frequency, duration, or date — which is why the AI responded by asking the user to confirm when their own appointment was. Both cases showed the same pattern: the AI produced plausible-sounding output that looked correct on inspection but broke on real use.

---

## RAG Enhancement — Custom Documents & Quality Measurement

The retrieval system was extended beyond the static built-in knowledge base to support custom documents from any source, and a quality evaluator was added to make improvement measurable.

### What was added

| Component | File | Purpose |
|-----------|------|---------|
| **Ingestion module** | `rag/ingest.py` | Chunk and index `.txt` / `.pdf` files at runtime |
| **Evaluator** | `rag/evaluator.py` | Score retrieval quality with keyword coverage and similarity metrics |
| **Vector store — new functions** | `rag/vector_store.py` | `list_sources()`, `delete_by_source()`, `count_by_category()` |
| **Pipeline — new function** | `rag/pipeline.py` | `retrieve()` — retrieval-only call for debugging and evaluation |
| **Upload UI** | `pages/Pet_Care_Assistant.py` | Sidebar file uploader, live source list with delete, per-response confidence bar |

### How to use custom documents

In the AI Chat sidebar, a **Custom Documents** panel accepts any `.txt` or `.pdf` file:

1. Upload a file — it is chunked, embedded, and upserted into ChromaDB immediately.
2. Ask questions — the system retrieves from *all* sources (built-in + custom) in the same cosine search.
3. Custom sources appear with a green `📎` pill on answers that used them.
4. Remove a source with the `✕` button; all its chunks are deleted from the vector store.

PDF support requires `pypdf` (`pip install pypdf`).

### How quality is measured

Every response now shows a **retrieval confidence bar** — the mean cosine-similarity score of the top-5 retrieved chunks, displayed as a percentage with a color-coded fill:

| Score | Colour | Meaning |
|-------|--------|---------|
| ≥ 70% | Green  | Chunks are semantically close to the query |
| 50–69% | Yellow | Moderate match; answer may be less specific |
| < 50% | Red    | Weak match; knowledge base may lack coverage |

The **Retrieval Quality Evaluation** panel (expandable, below the metrics row) runs an 8-question reference suite and reports two aggregate metrics:

- **Keyword coverage** — fraction of expected topic keywords found in the top-5 chunks
- **Avg similarity score** — mean cosine similarity across all retrieved chunks

### Testing with custom documents

Two ready-made profile documents are included in the repo — `oreo_profile.txt` (dog) and `oscar_profile.txt` (cat). Upload one or both through the sidebar **Custom Documents** panel, then use the questions below to verify the system is reading from them.

**After uploading `oreo_profile.txt`**

| Question | What it checks |
|---|---|
| "When is Oreo's next rabies vaccine due?" | Vaccination record — specific date retrieval |
| "What food does Oreo eat and how much?" | Feeding plan — quantity and brand |
| "What should Oreo never eat?" | Toxic foods list specific to Oreo |
| "What flea prevention does Oreo take?" | Medication retrieval |
| "Is Oreo spayed or neutered?" | Medical history |
| "Oreo has a bloated stomach and keeps retching — what should I do?" | Emergency symptoms — the most important test; before uploading the doc the system gives a generic answer, after it should name bloat specifically and direct to Dr. James Wilson |

**After uploading `oscar_profile.txt`**

| Question | What it checks |
|---|---|
| "What vaccines does Oscar need?" | Cat-specific vaccination schedule |
| "Oscar hasn't urinated in 12 hours — is that an emergency?" | Cat-specific emergency (urinary blockage) |
| "Are lilies dangerous for Oscar?" | Plant toxicity specific to cats |
| "How much should I feed Oscar?" | Feeding plan — weight and timing |
| "Does Oscar get along with Oreo?" | Behavioral notes across two pets |

**What good results look like**

- Source pill shows `📎 oreo_profile` or `📎 oscar_profile` — confirming the custom document was used, not the generic dogs/cats guide
- Retrieval confidence jumps from ~50% (generic guide) to ~75–85% (specific profile) because the chunk content closely matches the question
- Answers include specific details — vaccine brand names, exact gram amounts, named emergency symptoms — that the built-in knowledge base does not contain

### Before / after: adding a custom document

The improvement is most visible when a user asks about a topic not well covered by the built-in KB — for example, a breed-specific care guide or a custom vaccination record.

**Without custom document** — question: *"What are the care requirements for a Siberian Husky?"*

```
Retrieval confidence: 52%
Sources: 📖 Dogs  (generic breed section, partial match)
Answer:  "Dogs generally need 30–60 minutes of exercise daily. High-energy breeds
          like Huskies may need 1–2 hours..."
```

**After uploading** `husky_care_guide.txt` (a detailed Husky-specific guide):

```
Retrieval confidence: 87%
Sources: 📎 Husky Care Guide  📖 Dogs
Answer:  "Siberian Huskies need 1.5–2 hours of vigorous exercise daily and thrive
          in cold climates. Their double coat requires brushing 2–3 times per week,
          with heavy shedding seasons in spring and autumn..."
```

The confidence score jumps from 52 % to 87 % because the custom document provides exact, on-topic content. The answer shifts from generic to specific without any change to the pipeline — retrieval quality drives output quality.

### Running the evaluator programmatically

```python
from rag.evaluator import run_eval_suite, evaluate_question

# Full 8-question suite
results = run_eval_suite()
print(f"Coverage:   {results['avg_keyword_coverage']:.0%}")
print(f"Similarity: {results['avg_similarity_score']:.0%}")

# Single question with custom expected keywords
r = evaluate_question(
    "Husky exercise needs",
    expected_keywords=["husky", "exercise", "hours", "energy"],
)
print(r["keyword_coverage"], r["avg_similarity"])
```

### Ingesting documents programmatically

```python
from rag import ingest_file, ingest_text, remove_source

# From a file on disk
n = ingest_file("my_notes.txt", source_name="My Notes")
print(f"Indexed {n} chunks")

# From a string
n = ingest_text("Max had his rabies booster on 2025-03-10.", source_name="Max Records")

# Remove when no longer needed
remove_source("Max Records")
```

---

## Docs

| Document | Contents |
|----------|----------|
| [Architecture](docs/architecture.md) | UML class diagrams, component map, data-flow sequences |
| [Scheduling](docs/scheduling.md) | Scheduler, conflict detection, time-aware slot placement |
| [Testing](docs/testing.md) | Test distribution, edge case coverage, coverage report |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit ≥ 1.36 |
| Domain Model | Pure Python 3.12 |
| Embeddings | `sentence-transformers` · `all-MiniLM-L6-v2` |
| Vector DB | ChromaDB ≥ 0.5 |
| LLM Runtime | Ollama `llama3.2` (local) |
| Persistence | JSON |
| Tests | pytest ≥ 7.0 |
| PDF Parsing | pypdf ≥ 4.0 |

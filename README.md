# PawPal+

> AI-powered pet care scheduling — built with a local RAG pipeline and a Streamlit interface.

PawPal+ helps busy pet owners build realistic, conflict-free daily care plans. At its core is an embedded AI assistant that answers pet care questions and surfaces vet information from a curated knowledge base — entirely offline, no cloud API key required.

---

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set up the AI assistant (one-time)
python setup_rag.py

# Launch
streamlit run app.py
```

> Ollama is required for full AI responses. Install it from [ollama.com](https://ollama.com), then run `ollama pull llama3.2`. The app works offline too — it falls back to raw knowledge base excerpts when Ollama is unreachable.

---

## System Diagram

The diagram below shows the full end-to-end system — every major component, how data flows between them, and where humans and the test suite are involved in validating AI output.

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

    %% RAG data flow
    Q_INPUT --> EMB
    VDB -->|"Top-5 chunks"| PROMPT
    LLM -->|"grounded answer"| AI_OUT["💬 AI Answer + source pills"]
    FALLBACK -->|"excerpts + warning badge"| AI_OUT

    %% Scheduling data flow
    S_INPUT --> SCHED
    SLOTS --> CONFLICT

    %% Human review
    AI_OUT --> HUMAN["👤 Human Review"]
    SUGGEST --> HUMAN
    HUMAN -->|"source verification\n— trust signal from RAG"| AI_OUT
    HUMAN -->|"accept auto-fix or\nmanual override"| SLOTS

    %% Test suite validates backend
    TESTER -.->|"validates"| SCHEDULER
    TESTER -.->|"validates"| EVALUATOR
```

| Zone | What happens |
|------|-------------|
| **Retriever** | Embeds the user's question and pulls the top-5 semantically closest chunks from ChromaDB |
| **Agent / LLM** | Builds a grounded prompt and generates an answer locally; falls back to raw excerpts when Ollama is offline |
| **Scheduling Engine** | Builds a 7-day plan respecting recurrence, calendar blocks, and busy windows |
| **Evaluator** | Detects time overlaps, classifies severity, and suggests a priority-aware fix |
| **Human Review** | Owner verifies AI source pills, accepts or overrides the auto-fix, and stays in the loop for all AI-generated output |
| **Test Suite** | 131 automated tests continuously validate the scheduling engine and evaluator (100% backend coverage) |

---

## AI Assistant — RAG Pipeline

The AI chat feature is built on a local Retrieval-Augmented Generation pipeline. When a user asks a question, the system:

1. Embeds the question using `all-MiniLM-L6-v2` (384-dim vectors)
2. Retrieves the top-5 most relevant chunks from ChromaDB using cosine similarity
3. Builds a grounded prompt with owner/pet context
4. Generates an answer via a local Ollama `llama3.2` model

No data ever leaves the machine.

```
User question
      │
      ▼
  Embedder (all-MiniLM-L6-v2)
      │
      ▼
  ChromaDB  ──►  Top-5 chunks
      │
      ▼
  Prompt builder  +  Owner/Pet context
      │
      ├──  Ollama online  ──►  LLM answer  +  source pills
      │
      └──  Ollama offline  ──►  Raw KB excerpts  +  warning badge
```

### Knowledge Base

| Category | Files | Content |
|----------|:-----:|---------|
| Pet Care | 5 | Species guides — nutrition, exercise, grooming, health, behaviour |
| Veterinarians | 6 | Doctor profiles — specialisations, hours, fees, booking contacts |
| **Total** | **11** | ~300+ chunks · 200-word chunks · 30-word overlap |

```
knowledge_base/
├── pet_care/       dogs · cats · birds · rabbits · fish
└── doctors/        6 vet profiles
```

### RAG Modules

| Module | Role |
|--------|------|
| `rag/embedder.py` | Lazy-loads `all-MiniLM-L6-v2`; returns 384-dim float vectors |
| `rag/vector_store.py` | ChromaDB wrapper — `upsert`, `query` (cosine), `count`; persists to `chroma_db/` |
| `rag/llm.py` | Posts to Ollama REST API; returns `None` on `ConnectionError` |
| `rag/pipeline.py` | Orchestrates retrieval → prompt → LLM → fallback; single public `ask()` function |
| `setup_rag.py` | One-time indexer — reads KB files, chunks, embeds, upserts |

---

## Scheduling Engine

The scheduler builds a 7-day care plan and detects time conflicts:

- **Priority-based ordering** — `high → medium → low` within each day
- **Recurrence filtering** — daily / weekly (Mondays) / monthly (1st) tasks
- **Calendar-aware** — skips days blocked by events or holidays
- **Multi-pet** — aggregates tasks across all pets for one owner
- **Conflict detection** — O(n²) pairwise overlap check, severity-classified (Minor / Moderate / Major)
- **One-click auto-fix** — shortens the lower-priority conflicting task by the overlap duration

→ [Full scheduling & conflict detection docs](docs/scheduling.md)

---

## Project Structure

```
applied-ai-system-project/
├── app.py                     Navigation entrypoint
├── pages/
│   ├── Home.py                Scheduling dashboard
│   └── Pet_Care_Assistant.py  AI chat interface
├── pawpal_system.py           Domain model & scheduling engine
├── rag/                       RAG pipeline (5 modules)
├── knowledge_base/            11 plain-text documents
├── chroma_db/                 Persisted vector index (auto-created)
├── setup_rag.py               One-time KB indexer
├── tests/                     131 pytest tests · 100% backend coverage
└── pawpal_data.json           Runtime JSON store (auto-created)
```

---

## Tests & Coverage

```bash
python -m pytest          # 131 tests, all passing
python -m pytest --cov=pawpal_system --cov-report=term-missing
```

| Module | Statements | Coverage |
|--------|:----------:|:--------:|
| `pawpal_system.py` | 168 | **100%** |

→ [Full test breakdown](docs/testing.md)

---

## Architecture Docs

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

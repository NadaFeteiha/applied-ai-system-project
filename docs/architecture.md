# Architecture

← [Back to README](../README.md)

---

## Table of Contents

1. [Class Diagram — Initial Design](#class-diagram--initial-design)
2. [Class Diagram — Final Implementation](#class-diagram--final-implementation)
3. [Class Responsibilities](#class-responsibilities)
4. [Key Design Decisions](#key-design-decisions)
5. [Component Map](#component-map)
6. [Data Flow — Scheduling](#data-flow--scheduling)
7. [Data Flow — AI Assistant](#data-flow--ai-assistant)

---

## Class Diagram — Initial Design

Drafted during the design phase, before implementation began.

```mermaid
classDiagram
    class Owner {
        +String name
        +List~TimeSlot~ available_time
        +Dict preferences
        +Calendar calendar
        +List~Pet~ pets
        +get_info()
        +get_available_time() List~TimeSlot~
        +get_preferences() Dict
        +get_calendar() Calendar
        +add_pet(pet: Pet)
        +remove_pet(pet: Pet)
    }

    class Pet {
        +String name
        +String species
        +int age
        +get_info()
        +get_care_requirements() List~Task~
        +get_preferences() Dict
    }

    class Task {
        +String name
        +int duration
        +String priority
        +String frequency
        +get_info()
        +get_duration() int
        +get_priority() String
        +get_frequency() String
    }

    class Tracker {
        +List~Task~ tasks
        +add_task(task: Task)
        +edit_task(task: Task)
        +remove_task(task: Task)
        +get_tasks_for_day(date: Date) List~Task~
        +mark_task_completed(task: Task, date: Date)
        +send_reminder(task: Task, date: Date)
        +get_upcoming_tasks(date: Date) List~Task~
    }

    class Scheduler {
        +schedule_tasks(owner: Owner, pet: Pet, tasks: List~Task~) Schedule
        +explain_schedule(schedule: Schedule) String
    }

    class Calendar {
        +List~Event~ events
        +List~Date~ holidays
        +add_event(event: Event)
        +get_unavailable_times() List~TimeSlot~
        +is_available(date: Date) bool
    }

    Owner "1..*" -- "1..*" Pet : owns / shared care
    Pet "1" --> "1" Tracker : tracked by
    Tracker "1" o-- "many" Task : manages
    Owner "1" --> "1" Calendar : has
    Scheduler ..> Owner : uses
    Scheduler ..> Pet : uses
    Scheduler ..> Task : schedules
    Scheduler ..> Calendar : consults
```

---

## Class Diagram — Final Implementation

Reflects the actual class structure after implementation — all attributes, methods, and relationships included.

![PawPal+ Final UML Diagram](../uml_final.png)

```mermaid
classDiagram

    class TimeSlot {
        +str start
        +str end
        +__repr__() str
    }

    class Event {
        +str title
        +date day
        +TimeSlot slot
        +__repr__() str
    }

    class Task {
        +str name
        +int duration
        +str priority
        +str frequency
        +Optional~date~ active_from
        +get_info() Dict
        +next_occurrence_after(completed_on: date) Optional~date~
        +__repr__() str
    }

    class Tracker {
        +List~Task~ tasks
        +Dict completion_log
        +add_task(task: Task)
        +edit_task(updated_task: Task)
        +remove_task(task: Task)
        +get_tasks_for_day(day: date) List~Task~
        +mark_task_completed(task: Task, day: date)
        +send_reminder(task: Task, day: date, owners: List~Owner~)
        +get_upcoming_tasks(day: date) List~Task~
    }

    class Pet {
        +str name
        +str species
        +int age
        +Tracker tracker
        +List~Owner~ owners
        +get_info() Dict
        +get_care_requirements() List~Task~
        +get_preferences() Dict
        +__repr__() str
    }

    class Calendar {
        +List~Event~ events
        +List~date~ holidays
        +add_event(event: Event)
        +get_unavailable_times() List~TimeSlot~
        +is_available(day: date) bool
    }

    class Owner {
        +str name
        +List~TimeSlot~ available_time
        +Dict preferences
        +Calendar calendar
        +List~Pet~ pets
        +get_info() Dict
        +get_available_time() List~TimeSlot~
        +get_preferences() Dict
        +get_calendar() Calendar
        +add_pet(pet: Pet)
        +remove_pet(pet: Pet)
        +__repr__() str
    }

    class Schedule {
        +Owner owner
        +List~Pet~ pets
        +Dict~date, List~ plan
        +add_entry(day: date, pet: Pet, task: Task)
    }

    class Scheduler {
        -Dict _PRIORITY_ORDER
        +schedule_tasks(owner: Owner, pets: List~Pet~) Schedule
        +complete_task(task: Task, pet: Pet, day: date) Optional~date~
        +explain_schedule(schedule: Schedule) str
    }

    Owner "1" *-- "1" Calendar : has
    Owner "1" *-- "0..*" TimeSlot : available_time
    Calendar "1" *-- "0..*" Event : contains
    Event "1" *-- "1" TimeSlot : occupies
    Pet "1" *-- "1" Tracker : has
    Tracker "1" *-- "0..*" Task : tracks
    Owner "0..*" -- "0..*" Pet : owns / owned by
    Schedule "1" --> "1" Owner : for
    Schedule "1" --> "0..*" Pet : covers
    Scheduler ..> Schedule : creates
    Scheduler ..> Owner : reads
    Scheduler ..> Pet : reads
    Scheduler ..> Task : reads
```

---

## Class Responsibilities

| Class | Responsibility |
|-------|----------------|
| **TimeSlot** | Represents a `start`–`end` time window (e.g. `"09:00"`). |
| **Event** | A named calendar event tied to a specific day and time slot. |
| **Task** | A care task with name, duration, priority, frequency, and optional `active_from` for deferred scheduling. |
| **Tracker** | Manages a pet's task list and completion log; handles auto-rescheduling via `active_from`. |
| **Pet** | A pet with species, age, and an embedded `Tracker`; participates in a many-to-many relationship with `Owner`. |
| **Calendar** | Stores events and holidays for an owner; answers availability queries. |
| **Owner** | A pet owner with available time slots, preferences, a `Calendar`, and a list of pets. |
| **Schedule** | Output of scheduling: a day-keyed plan of `(Pet, Task)` pairs for a given owner. |
| **Scheduler** | Stateless service that builds a 7-day `Schedule`, marks tasks complete, and produces human-readable summaries. |

---

## Key Design Decisions

- **Many-to-many Owner ↔ Pet** — `Owner.add_pet()` and `Owner.remove_pet()` keep both sides (`owner.pets` and `pet.owners`) in sync.
- **Deferred scheduling via `active_from`** — When a task is marked complete, `Tracker.mark_task_completed()` replaces it with a new instance whose `active_from` is the next due date, hiding it until then.
- **Priority ordering** — `Scheduler._PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}` drives sort order inside `schedule_tasks()`.
- **Conflict detection** (`app.py`) — `_detect_conflicts()` scans all scheduled slots for overlapping pairs using an O(n²) pairwise check.
- **Slot builder** (`app.py`) — `_build_slots()` separates single-occurrence tasks (stacked sequentially) from multi-occurrence tasks (spread proportionally across free blocks).

---

## Component Map

```mermaid
graph TB
    subgraph NAV_LAYER["Navigation  (app.py)"]
        NAV["st.navigation"]
    end

    subgraph UI_LAYER["UI Pages  (pages/)"]
        HOME["Home.py — Scheduling Dashboard"]
        CHAT["Pet_Care_Assistant.py — AI Chat"]
    end

    subgraph DOMAIN_LAYER["Domain Model  (pawpal_system.py)"]
        OWNER["Owner"]
        PET["Pet"]
        TRACKER["Tracker"]
        TASK["Task"]
        CAL["Calendar"]
        SCHED["Scheduler"]
        OWNER --> PET --> TRACKER --> TASK
        OWNER --> CAL
        SCHED --> OWNER
        SCHED --> PET
    end

    subgraph RAG_LAYER["RAG Pipeline  (rag/)"]
        PIPE["pipeline.py — Orchestrator"]
        EMB["embedder.py — all-MiniLM-L6-v2"]
        VEC["vector_store.py — ChromaDB"]
        LLM["llm.py — Ollama llama3.2"]
        PIPE --> EMB --> VEC
        PIPE --> LLM
    end

    subgraph DATA_LAYER["Data Layer"]
        JSON_DB["pawpal_data.json"]
        CHROMA_DB[("chroma_db/")]
        KB_FILES["knowledge_base/  (11 files)"]
    end

    NAV --> HOME
    NAV --> CHAT
    HOME <--> DOMAIN_LAYER
    HOME <--> JSON_DB
    CHAT --> PIPE
    VEC <--> CHROMA_DB
    KB_FILES -. "setup_rag.py (one-time)" .-> VEC
```

---

## Data Flow — Scheduling

```mermaid
sequenceDiagram
    actor User
    participant UI  as Home.py
    participant DB  as pawpal_data.json
    participant ENG as Scheduling Engine

    User ->> UI  : Add owner / pet / task
    UI   ->> DB  : JSON write (_save)

    User ->> UI  : View 7-day schedule
    UI   ->> DB  : Load owner data
    UI   ->> ENG : _tasks_due_on(pets, day)
    ENG -->> UI  : Filtered & priority-sorted entries

    UI   ->> ENG : _build_slots(entries, free_blocks)
    ENG -->> UI  : Time-placed slot list

    UI   ->> ENG : _detect_conflicts(slots)
    ENG -->> UI  : Conflict pairs + severity labels

    UI  -->> User : Rendered schedule + conflict banners
```

---

## Data Flow — AI Assistant

```mermaid
sequenceDiagram
    actor User
    participant CHAT as Pet_Care_Assistant.py
    participant PIPE as pipeline.py
    participant EMB  as embedder.py
    participant VEC  as vector_store.py (ChromaDB)
    participant LLM  as llm.py (Ollama)

    User ->> CHAT : Ask a question
    CHAT ->> PIPE : ask(question, user_context)

    PIPE ->> EMB  : embed([question])
    EMB -->> VEC  : 384-dim query vector
    VEC -->> PIPE : Top-5 chunks (cosine similarity + score)

    PIPE ->> PIPE : _build_prompt(question, chunks, context)

    alt Ollama online
        PIPE ->> LLM  : generate(prompt)
        LLM -->> PIPE : Grounded answer string
        PIPE -->> CHAT : { answer, sources, llm_used: true }
    else Ollama offline
        PIPE -->> CHAT : { answer: raw excerpts, sources, llm_used: false }
    end

    CHAT -->> User : Answer + source pills
```

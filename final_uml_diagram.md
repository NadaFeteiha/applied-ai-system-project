# PawPal+ — Final UML Class Diagram

```mermaid
classDiagram

    %% ─────────────────────────────────────────────
    %% Core Domain Classes  (pawpal_system.py)
    %% ─────────────────────────────────────────────

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

    %% ─────────────────────────────────────────────
    %% Relationships
    %% ─────────────────────────────────────────────

    %% Composition / Ownership
    Owner "1" *-- "1" Calendar : has
    Owner "1" *-- "0..*" TimeSlot : available_time
    Calendar "1" *-- "0..*" Event : contains
    Event "1" *-- "1" TimeSlot : occupies
    Pet "1" *-- "1" Tracker : has
    Tracker "1" *-- "0..*" Task : tracks

    %% Many-to-Many: Owner ↔ Pet
    Owner "0..*" -- "0..*" Pet : owns / owned by

    %% Schedule associations
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
|-------|---------------|
| **TimeSlot** | Represents a `start`–`end` time window (strings like `"09:00"`). |
| **Event** | A named calendar event tied to a specific day and `TimeSlot`. |
| **Task** | A care task with name, duration, priority, frequency, and optional `active_from` date for deferred scheduling. |
| **Tracker** | Manages a pet's task list and completion log; handles auto-rescheduling via `active_from`. |
| **Pet** | A pet with species, age, and an embedded `Tracker`; participates in a many-to-many relationship with `Owner`. |
| **Calendar** | Stores events and holidays for an owner; answers availability queries. |
| **Owner** | A pet owner with available time slots, preferences, a `Calendar`, and a list of pets. |
| **Schedule** | The output of scheduling: a day-keyed plan of `(Pet, Task)` pairs for a given owner. |
| **Scheduler** | Stateless service that builds a 7-day `Schedule`, marks tasks complete, and produces human-readable summaries. |

---

## Key Design Decisions

- **Many-to-many Owner ↔ Pet**: `Owner.add_pet()` / `Owner.remove_pet()` keep both sides (`owner.pets` and `pet.owners`) in sync.
- **Deferred scheduling via `active_from`**: When a task is marked complete, `Tracker.mark_task_completed()` replaces it with a new instance whose `active_from` is set to the next due date, hiding it until then.
- **Priority ordering**: `Scheduler._PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}` drives sort order inside `schedule_tasks()` and the app-level `_tasks_due_on()`.
- **Conflict detection** (`app.py`): `_detect_conflicts()` scans all scheduled slots for overlapping `_start_raw`/`_end_raw` pairs (O(n²) pairwise check).
- **Scheduling engine** (`app.py`): `_build_slots()` separates single-occurrence tasks (stacked sequentially) from multi-occurrence tasks (spread proportionally across free blocks by duration).

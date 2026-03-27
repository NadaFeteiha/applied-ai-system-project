# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

so I will need owner that will have account and could be able to have multiple pets, and each pet will have its own set of tasks, and the scheduler will need to consider the owner's available time and preferences when generating a daily plan.

Also should be abele that the pet could have multiple owner so they could share the care tasks and schedule.

there will be a Tracker class that will manage the tasks for each pet and each day because some tasks are daily and some are weekly or monthly, and the Scheduler class will need to consider the frequency of each task when generating the schedule.

the scheduler need to have access to the owner's calendar to avoid scheduling tasks during times when the owner is unavailable and also to consider the holidays or special events that might affect services such as grooming or vet visits.

the tracker will also need to keep track of the completion status daily and able to send reminders to the owner for upcoming tasks or missed tasks.

the initial UML design included the following classes:

class Pet:
    - Attributes: name, species, age
    - Methods: get_info(), get_care_requirements(), get_preferences()

class Tracker:
    - Attributes: tasks (list of Task objects)
    - Methods: add_task(), edit_task(), remove_task(),get_tasks_for_day(date),mark_task_completed(task, date),send_reminder(task, date),get_upcoming_tasks(date)

class owner:
    - Attributes: name, available_time,preferences, calendar, pets (list of Pet objects)
    - Methods: get_info(),get_available_time(), get_preferences(), get_calendar(), add_pet(pet), remove_pet(pet)

class Scheduler:
    - Attributes: None (or any necessary attributes for scheduling)
    - Methods: schedule_tasks(owner, pet, tasks),explain_schedule(schedule)

class Task:
    - Attributes: name, duration, priority, frequency
    - Methods: get_info(), get_duration(), get_priority(), get_frequency()


**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

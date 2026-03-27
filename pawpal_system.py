from datetime import date
from typing import List, Dict


class Task:
    def __init__(self, name: str, duration: int, priority: str, frequency: str):
        self.name = name
        self.duration = duration      # in minutes
        self.priority = priority      # e.g. "high", "medium", "low"
        self.frequency = frequency    # e.g. "daily", "weekly", "monthly"

    def get_info(self) -> Dict:
        raise NotImplementedError

    def get_duration(self) -> int:
        raise NotImplementedError

    def get_priority(self) -> str:
        raise NotImplementedError

    def get_frequency(self) -> str:
        raise NotImplementedError


class Calendar:
    def __init__(self):
        self.events: List[Dict] = []
        self.holidays: List[date] = []

    def add_event(self, event: Dict):
        raise NotImplementedError

    def get_unavailable_times(self) -> List[Dict]:
        raise NotImplementedError

    def is_available(self, day: date) -> bool:
        raise NotImplementedError


class Pet:
    def __init__(self, name: str, species: str, age: int):
        self.name = name
        self.species = species
        self.age = age
        self.tracker: "Tracker" = Tracker()

    def get_info(self) -> Dict:
        raise NotImplementedError

    def get_care_requirements(self) -> List[Task]:
        raise NotImplementedError

    def get_preferences(self) -> Dict:
        raise NotImplementedError


class Owner:
    def __init__(self, name: str):
        self.name = name
        self.available_time: List[Dict] = []
        self.preferences: Dict = {}
        self.calendar: Calendar = Calendar()
        self.pets: List[Pet] = []

    def get_info(self) -> Dict:
        raise NotImplementedError

    def get_available_time(self) -> List[Dict]:
        raise NotImplementedError

    def get_preferences(self) -> Dict:
        raise NotImplementedError

    def get_calendar(self) -> Calendar:
        raise NotImplementedError

    def add_pet(self, pet: Pet):
        raise NotImplementedError

    def remove_pet(self, pet: Pet):
        raise NotImplementedError


class Tracker:
    def __init__(self):
        self.tasks: List[Task] = []

    def add_task(self, task: Task):
        raise NotImplementedError

    def edit_task(self, task: Task):
        raise NotImplementedError

    def remove_task(self, task: Task):
        raise NotImplementedError

    def get_tasks_for_day(self, day: date) -> List[Task]:
        raise NotImplementedError

    def mark_task_completed(self, task: Task, day: date):
        raise NotImplementedError

    def send_reminder(self, task: Task, day: date):
        raise NotImplementedError

    def get_upcoming_tasks(self, day: date) -> List[Task]:
        raise NotImplementedError


class Scheduler:
    def schedule_tasks(self, owner: Owner, pet: Pet, tasks: List[Task]) -> Dict:
        raise NotImplementedError

    def explain_schedule(self, schedule: Dict) -> str:
        raise NotImplementedError

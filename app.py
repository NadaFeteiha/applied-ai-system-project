import json
import calendar
import streamlit as st
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from pawpal_system import Owner, Pet, Task, Scheduler, TimeSlot

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")

DATA_FILE = Path("pawpal_data.json")

SPECIES_EMOJI = {
    "dog": "🐶", "cat": "🐱", "bird": "🐦",
    "rabbit": "🐰", "fish": "🐟", "other": "🐾",
}
PRIORITY_COLOR = {"high": "🔴", "medium": "🟡", "low": "🟢"}
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"owners": {}}


def _save():
    DATA_FILE.write_text(json.dumps(st.session_state.db, indent=2))


def _init():
    if "db" not in st.session_state:
        st.session_state.db = _load()


def _parse_time(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def _add_minutes(t: dtime, minutes: int) -> dtime:
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time().replace(second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Build domain objects from stored JSON
# ---------------------------------------------------------------------------

def build_owner(name: str) -> Owner:
    owner = Owner(name)
    owner_data = st.session_state.db["owners"].get(name, {})
    weekly = owner_data.get("weekly_availability", {})

    if weekly:
        today = date.today()
        for i in range(7):
            day = today + timedelta(days=i)
            day_name = day.strftime("%A")
            day_cfg = weekly.get(day_name, {"available": True})
            if not day_cfg.get("available", True):
                owner.calendar.holidays.append(day)
            else:
                start = day_cfg.get("start", "00:00")
                end = day_cfg.get("end", "23:59")
                owner.available_time.append(TimeSlot(start, end))

    for pd in owner_data.get("pets", []):
        pet = Pet(pd["name"], pd["species"], pd["age"])
        for td in pd.get("tasks", []):
            pet.tracker.add_task(Task(td["name"], td["duration"], td["priority"], td["frequency"]))
        owner.add_pet(pet)
    return owner


def owner_names() -> list:
    return list(st.session_state.db["owners"].keys())


def pet_names(owner_name: str) -> list:
    return [p["name"] for p in st.session_state.db["owners"].get(owner_name, {}).get("pets", [])]


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _owner_free_blocks(owner_name: str, day_name: str) -> list[tuple[dtime, dtime]]:
    """
    Return a list of (start, end) free-time blocks for the owner on a given weekday.
    If a busy block is configured (e.g. 08:00–17:00), the free blocks are split:
      [day_start → busy_start] and [busy_end → day_end].
    """
    weekly = st.session_state.db["owners"].get(owner_name, {}).get("weekly_availability", {})
    cfg = weekly.get(day_name, {})
    day_start = _parse_time(cfg.get("start", "08:00"))
    day_end = _parse_time(cfg.get("end", "20:00"))

    if cfg.get("has_busy_block"):
        busy_start = _parse_time(cfg.get("busy_start", "08:00"))
        busy_end = _parse_time(cfg.get("busy_end", "17:00"))
        blocks = []
        if day_start < busy_start:
            blocks.append((day_start, busy_start))
        if busy_end < day_end:
            blocks.append((busy_end, day_end))
        return blocks if blocks else [(day_start, day_end)]

    return [(day_start, day_end)]


def _weekly_task_weekdays(owner_name: str, times_per_week: int) -> set:
    """
    Return weekday numbers (0=Mon … 6=Sun) on which a weekly task should appear,
    evenly spread across the owner's available days.
    """
    weekly = st.session_state.db["owners"].get(owner_name, {}).get("weekly_availability", {})
    avail = [i for i, d in enumerate(DAYS_OF_WEEK) if weekly.get(d, {}).get("available", True)]
    if not avail:
        avail = list(range(7))
    n = min(max(1, times_per_week), len(avail))
    k = len(avail)
    if n >= k:
        return set(avail)
    if n == 1:
        return {avail[0]}
    indices = [round(i * (k - 1) / (n - 1)) for i in range(n)]
    return {avail[idx] for idx in indices}


def _is_owner_available_on(owner_name: str, day: date) -> bool:
    """Check weekly_availability for a specific date."""
    weekly = st.session_state.db["owners"].get(owner_name, {}).get("weekly_availability", {})
    if not weekly:
        return True  # no restrictions set → always available
    day_name = day.strftime("%A")
    return weekly.get(day_name, {}).get("available", True)


def _tasks_due_on(pets_data: list, day: date, owner_name=None) -> list[tuple]:
    """Return [(pet_name, species, task_dict), ...] sorted by priority for a given date."""
    due = []
    for p in pets_data:
        for t in p.get("tasks", []):
            if t["frequency"] == "daily":
                due.append((p["name"], p["species"], t))
            elif t["frequency"] == "weekly":
                tpw = t.get("times_per_week", 1)
                if owner_name and tpw > 1:
                    scheduled_days = _weekly_task_weekdays(owner_name, tpw)
                else:
                    scheduled_days = {0}  # default: Monday only
                if day.weekday() in scheduled_days:
                    due.append((p["name"], p["species"], t))
            elif t["frequency"] == "monthly" and day.day == 1:
                due.append((p["name"], p["species"], t))
    due.sort(key=lambda x: PRIORITY_ORDER.get(x[2]["priority"], 3))
    return due


def _block_minutes(s: dtime, e: dtime) -> int:
    return max(1, int((datetime.combine(date.today(), e) - datetime.combine(date.today(), s)).total_seconds() // 60))


def _distribute_occurrences(n: int, bm_list: list[int]) -> list[int]:
    """Proportionally distribute n occurrences across blocks of sizes bm_list."""
    total = sum(bm_list)
    raw = [n * bm / total for bm in bm_list]
    counts = [int(r) for r in raw]
    remainder = n - sum(counts)
    fractions = sorted(enumerate(raw), key=lambda x: -(x[1] - int(x[1])))
    for j in range(remainder):
        counts[fractions[j][0]] += 1
    return counts


def _build_slots(entries, free_blocks, keep_meta: bool) -> list[dict]:
    """
    Core scheduling engine.  Distributes task occurrences across free time blocks.

    - Single-occurrence tasks are stacked sequentially from the first block's start.
    - Multi-occurrence tasks are spread evenly, one occurrence centered per sub-interval,
      across free blocks weighted by block duration.
    """
    if not free_blocks:
        return []

    slots = []
    single = [(p, sp, t) for p, sp, t in entries if t.get("times_per_day", 1) <= 1]
    multi  = [(p, sp, t) for p, sp, t in entries if t.get("times_per_day", 1) > 1]

    # ── Single-occurrence tasks: stack sequentially, advancing through blocks ──
    blk_idx = 0
    cursor = free_blocks[0][0]
    for pet_name, species, t in single:
        task_end = _add_minutes(cursor, t["duration"])
        # Advance to next block if this task overflows the current one
        while blk_idx < len(free_blocks) - 1:
            _, blk_end = free_blocks[blk_idx]
            if datetime.combine(date.today(), task_end) > datetime.combine(date.today(), blk_end):
                blk_idx += 1
                cursor = free_blocks[blk_idx][0]
                task_end = _add_minutes(cursor, t["duration"])
            else:
                break
        slot = {
            "_sort": datetime.combine(date.today(), cursor),
            "_pet_raw": pet_name,
            "_task_raw": t["name"],
            "_dur_raw": t["duration"],
            "_priority_raw": t["priority"],
            "_start_raw": cursor,
            "_end_raw": task_end,
            "Pet": f"{SPECIES_EMOJI.get(species, '🐾')} {pet_name}",
            "Task": t["name"],
            "Occurrence": "—",
            "Priority": PRIORITY_COLOR.get(t["priority"], "⚪") + " " + t["priority"],
            "Start": cursor.strftime("%I:%M %p"),
            "End": task_end.strftime("%I:%M %p"),
            "Duration": f"{t['duration']} min",
        }
        slots.append(slot)
        cursor = task_end

    # ── Multi-occurrence tasks: spread across blocks, centered within sub-intervals ──
    bm_list = [_block_minutes(s, e) for s, e in free_blocks]
    for pet_name, species, t in multi:
        n = t.get("times_per_day", 1)
        counts = _distribute_occurrences(n, bm_list)
        occ_global = 0
        for bi, (blk_start, _blk_end) in enumerate(free_blocks):
            n_in_blk = counts[bi]
            if n_in_blk == 0:
                continue
            bm = bm_list[bi]
            interval = bm / n_in_blk
            for i in range(n_in_blk):
                # Center each occurrence within its sub-interval
                offset = int(i * interval + interval / 2)
                occ_start = _add_minutes(blk_start, offset)
                occ_end = _add_minutes(occ_start, t["duration"])
                occ_global += 1
                slot = {
                    "_sort": datetime.combine(date.today(), occ_start),
                    "_pet_raw": pet_name,
                    "_task_raw": t["name"],
                    "_dur_raw": t["duration"],
                    "_priority_raw": t["priority"],
                    "_start_raw": occ_start,
                    "_end_raw": occ_end,
                    "Pet": f"{SPECIES_EMOJI.get(species, '🐾')} {pet_name}",
                    "Task": t["name"],
                    "Occurrence": f"{occ_global}/{n}",
                    "Priority": PRIORITY_COLOR.get(t["priority"], "⚪") + " " + t["priority"],
                    "Start": occ_start.strftime("%I:%M %p"),
                    "End": occ_end.strftime("%I:%M %p"),
                    "Duration": f"{t['duration']} min",
                }
                slots.append(slot)

    slots.sort(key=lambda x: x["_sort"])
    if not keep_meta:
        for s in slots:
            for k in ["_sort", "_pet_raw", "_task_raw", "_dur_raw", "_priority_raw",
                      "_start_raw", "_end_raw"]:
                s.pop(k, None)
    else:
        for s in slots:
            del s["_sort"]
    return slots


def _assign_times(entries: list[tuple], free_blocks: list[tuple]) -> list[dict]:
    """Assign scheduled times to tasks across free_blocks; strips internal metadata."""
    return _build_slots(entries, free_blocks, keep_meta=False)


def _assign_times_with_meta(entries, free_blocks: list[tuple]) -> list[dict]:
    """Same as _assign_times but keeps raw metadata keys for sorting/filtering."""
    return _build_slots(entries, free_blocks, keep_meta=True)


def _detect_conflicts(slots: list[dict]) -> list[tuple[dict, dict]]:
    """
    Return every pair of slots whose time windows overlap.
    Requires slots to have '_start_raw' and '_end_raw' (dtime) keys.
    Two tasks conflict when:  a.start < b.end  AND  b.start < a.end
    """
    conflicts = []
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            a, b = slots[i], slots[j]
            if a["_start_raw"] < b["_end_raw"] and b["_start_raw"] < a["_end_raw"]:
                conflicts.append((a, b))
    return conflicts


def _conflict_severity(overlap_min: int) -> tuple[str, str, str]:
    """Return (label, emoji, hex_color) based on overlap duration."""
    if overlap_min > 15:
        return "Major", "🔴", "#dc3545"
    elif overlap_min > 5:
        return "Moderate", "🟠", "#fd7e14"
    return "Minor", "🟡", "#ffc107"


def _priority_rank(priority: str) -> int:
    return PRIORITY_ORDER.get(priority, 3)


def _render_conflict_timeline_html(a: dict, b: dict, day_start: dtime, day_end: dtime) -> str:
    """Render an inline HTML bar visualising two overlapping task windows."""
    total_min = _block_minutes(day_start, day_end)
    if total_min <= 0:
        return ""

    def pct(t: dtime) -> float:
        return max(0.0, min(100.0, _block_minutes(day_start, t) / total_min * 100))

    a_s, a_e = pct(a["_start_raw"]), pct(a["_end_raw"])
    b_s, b_e = pct(b["_start_raw"]), pct(b["_end_raw"])
    ov_s, ov_e = max(a_s, b_s), min(a_e, b_e)

    bar_a  = f'<div style="position:absolute;left:{a_s:.1f}%;width:{a_e-a_s:.1f}%;height:100%;background:#4e8cff;opacity:0.75;border-radius:3px"></div>'
    bar_b  = f'<div style="position:absolute;left:{b_s:.1f}%;width:{b_e-b_s:.1f}%;height:100%;background:#28a745;opacity:0.75;border-radius:3px"></div>'
    bar_ov = f'<div style="position:absolute;left:{ov_s:.1f}%;width:{ov_e-ov_s:.1f}%;height:100%;background:#dc3545;opacity:0.95;border-radius:3px"></div>'

    return f"""
    <div style="margin:10px 0 6px 0">
      <div style="display:flex;justify-content:space-between;font-size:0.68em;color:#888;margin-bottom:3px">
        <span>{day_start.strftime("%I:%M %p")}</span><span>{day_end.strftime("%I:%M %p")}</span>
      </div>
      <div style="position:relative;height:22px;background:#e9ecef;border-radius:4px;overflow:hidden">
        {bar_a}{bar_b}{bar_ov}
      </div>
      <div style="display:flex;gap:14px;font-size:0.68em;margin-top:5px;color:#555">
        <span><span style="display:inline-block;background:#4e8cff;width:10px;height:10px;border-radius:2px;vertical-align:middle"></span>&nbsp;{a["_task_raw"]}</span>
        <span><span style="display:inline-block;background:#28a745;width:10px;height:10px;border-radius:2px;vertical-align:middle"></span>&nbsp;{b["_task_raw"]}</span>
        <span><span style="display:inline-block;background:#dc3545;width:10px;height:10px;border-radius:2px;vertical-align:middle"></span>&nbsp;Overlap</span>
      </div>
    </div>
    """


def _completion_key(pet_name: str, task_name: str) -> str:
    return f"{pet_name}::{task_name}"


def _is_complete(owner_name: str, pet_name: str, task_name: str, day_str: str) -> bool:
    completions = st.session_state.db["owners"].get(owner_name, {}).get("completions", {})
    return day_str in completions.get(_completion_key(pet_name, task_name), [])


def _toggle_complete(owner_name: str, pet_name: str, task_name: str, day_str: str):
    owner = st.session_state.db["owners"][owner_name]
    completions = owner.setdefault("completions", {})
    key = _completion_key(pet_name, task_name)
    days = completions.setdefault(key, [])
    if day_str in days:
        days.remove(day_str)
    else:
        days.append(day_str)
    _save()


def _build_month_task_map(owner_name: str, year: int, month: int) -> dict[date, list]:
    """Return {date: [task_entries]} for every day in the month where owner is available."""
    pets_data = st.session_state.db["owners"].get(owner_name, {}).get("pets", [])
    num_days = calendar.monthrange(year, month)[1]
    result = {}
    for d in range(1, num_days + 1):
        day = date(year, month, d)
        if not _is_owner_available_on(owner_name, day):
            continue
        entries = _tasks_due_on(pets_data, day, owner_name)
        if entries:
            result[day] = entries
    return result


def _render_calendar_html(year: int, month: int, task_map: dict[date, list]) -> str:
    """Build an HTML calendar grid for the month, marking days that have tasks."""
    today = date.today()
    month_name = date(year, month, 1).strftime("%B %Y")
    first_weekday, num_days = calendar.monthrange(year, month)
    # calendar.monthrange returns 0=Monday ... 6=Sunday

    header = "".join(
        f'<th style="padding:8px 4px;color:#667eea;font-size:0.78em;font-weight:700;letter-spacing:0.05em">{d}</th>'
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    )

    cells = ["<td></td>"] * first_weekday  # leading blank cells
    for d in range(1, num_days + 1):
        day = date(year, month, d)
        entries = task_map.get(day, [])
        is_today = day == today

        if is_today:
            border = "2px solid #34d399"
            bg = "rgba(52,211,153,0.1)"
            day_color = "#34d399"
        elif entries:
            border = "1px solid rgba(102,126,234,0.3)"
            bg = "rgba(102,126,234,0.06)"
            day_color = "#a5b4fc"
        else:
            border = "1px solid rgba(255,255,255,0.06)"
            bg = "rgba(255,255,255,0.02)"
            day_color = "#4b5563"

        task_html = ""
        for pet_name, species, t in entries[:3]:  # show up to 3 per cell
            dot = PRIORITY_COLOR.get(t["priority"], "⚪")
            task_html += f'<div style="font-size:0.62em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#9ca3af;margin-top:2px">{dot} {t["name"]}</div>'
        if len(entries) > 3:
            task_html += f'<div style="font-size:0.58em;color:#6b7280">+{len(entries)-3} more</div>'

        cells.append(
            f'<td style="border:{border};padding:6px;vertical-align:top;background:{bg};min-width:80px;height:70px;border-radius:8px">'
            f'<strong style="font-size:0.85em;color:{day_color}">{d}</strong>{task_html}</td>'
        )

    # Pad trailing cells
    remainder = len(cells) % 7
    if remainder:
        cells += ["<td></td>"] * (7 - remainder)

    rows_html = ""
    for i in range(0, len(cells), 7):
        rows_html += "<tr>" + "".join(cells[i:i+7]) + "</tr>"

    return f"""
    <h4 style="text-align:center;margin-bottom:12px;color:#a5b4fc;font-weight:700;font-size:1.2em;letter-spacing:-0.5px">{month_name}</h4>
    <table style="width:100%;border-collapse:separate;border-spacing:3px;text-align:center">
      <thead><tr style="background:rgba(102,126,234,0.15);border-radius:8px">{header}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    """


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_init()

# ── Custom CSS & Animations ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Global */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', sans-serif;
}
[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(160deg, #0d1117 0%, #161b27 40%, #1a1f35 100%);
    min-height: 100vh;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { background: #161b27 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a1f35; }
::-webkit-scrollbar-thumb { background: #667eea; border-radius: 3px; }

/* Animations */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(102,126,234,0.3); }
    50%       { box-shadow: 0 0 40px rgba(102,126,234,0.6); }
}
@keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position:  200% center; }
}
.fade-in { animation: fadeInUp 0.5s ease-out; }

/* Hero banner */
.hero-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 45%, #f64f59 100%);
    border-radius: 24px;
    padding: 48px 40px 40px;
    text-align: center;
    margin-bottom: 32px;
    box-shadow: 0 24px 64px rgba(102,126,234,0.35);
    animation: fadeInUp 0.7s ease-out, pulse-glow 4s ease-in-out infinite;
}
.hero-banner h1 {
    color: white; font-size: 3.2em; margin: 0; font-weight: 800;
    text-shadow: 0 2px 20px rgba(0,0,0,0.3);
    letter-spacing: -1px;
}
.hero-banner p {
    color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 10px 0 0;
    font-weight: 400;
}

/* Step badges */
.step-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: linear-gradient(90deg, #667eea, #764ba2);
    color: white; padding: 8px 20px; border-radius: 50px;
    font-size: 0.9em; font-weight: 700; margin-bottom: 12px;
    box-shadow: 0 4px 20px rgba(102,126,234,0.4);
    animation: fadeInUp 0.4s ease-out;
}

/* Pet cards */
.pet-card {
    background: linear-gradient(135deg, rgba(102,126,234,0.12), rgba(118,75,162,0.08));
    border: 1px solid rgba(102,126,234,0.25);
    border-radius: 20px; padding: 24px 16px; text-align: center;
    backdrop-filter: blur(12px); margin-bottom: 12px;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    animation: fadeInUp 0.45s ease-out;
    color: #e8eaf6;
}
.pet-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 16px 48px rgba(102,126,234,0.35);
    border-color: rgba(102,126,234,0.5);
}
.pet-card .emoji  { font-size: 3.2em; margin-bottom: 10px; display: block; }
.pet-card .name   { font-weight: 700; font-size: 1.15em; color: white; }
.pet-card .meta   { color: rgba(200,200,230,0.75); font-size: 0.82em; margin-top: 6px; }
.pet-card .badges { margin-top: 10px; }
.pet-card .badge  {
    display: inline-block; background: rgba(102,126,234,0.3);
    border: 1px solid rgba(102,126,234,0.4); border-radius: 20px;
    padding: 3px 12px; font-size: 0.78em; color: #a5b4fc; font-weight: 600;
}

/* Task cards */
.task-card {
    border-radius: 14px; padding: 14px 18px; margin-bottom: 10px;
    display: flex; align-items: center; gap: 14px;
    animation: fadeInUp 0.35s ease-out;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    cursor: default;
}
.task-card:hover { transform: translateX(6px); }
.task-high   { background: linear-gradient(90deg, rgba(220,53,69,0.18), rgba(220,53,69,0.06));
               border-left: 4px solid #dc3545; }
.task-medium { background: linear-gradient(90deg, rgba(251,191,36,0.18), rgba(251,191,36,0.06));
               border-left: 4px solid #fbbf24; }
.task-low    { background: linear-gradient(90deg, rgba(52,211,153,0.18), rgba(52,211,153,0.06));
               border-left: 4px solid #34d399; }
.task-done   { opacity: 0.45; }
.task-name   { font-weight: 600; font-size: 0.95em; color: white; flex: 1; }
.task-name s { color: #9ca3af; }
.task-meta   { font-size: 0.78em; color: #9ca3af; margin-top: 2px; }
.task-pill   {
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 20px; padding: 2px 10px; font-size: 0.74em;
    color: #c4c9d4; white-space: nowrap;
}
.priority-badge-high   { background: rgba(220,53,69,0.25);  color: #f87171; border-radius: 8px; padding: 2px 8px; font-size: 0.75em; font-weight: 700; }
.priority-badge-medium { background: rgba(251,191,36,0.25); color: #fbbf24; border-radius: 8px; padding: 2px 8px; font-size: 0.75em; font-weight: 700; }
.priority-badge-low    { background: rgba(52,211,153,0.25); color: #34d399; border-radius: 8px; padding: 2px 8px; font-size: 0.75em; font-weight: 700; }

/* Schedule cards */
.sched-card {
    border-radius: 12px; padding: 12px 16px; margin-bottom: 8px;
    display: grid; grid-template-columns: 1fr auto auto auto;
    align-items: center; gap: 12px;
    animation: fadeInUp 0.3s ease-out;
    transition: transform 0.15s ease;
}
.sched-card:hover { transform: translateX(4px); }
.sched-high   { background: rgba(220,53,69,0.12);  border-left: 3px solid #dc3545; }
.sched-medium { background: rgba(251,191,36,0.12); border-left: 3px solid #fbbf24; }
.sched-low    { background: rgba(52,211,153,0.12); border-left: 3px solid #34d399; }
.sched-done   { opacity: 0.4; }
.sched-name   { font-weight: 600; color: white; font-size: 0.92em; }
.sched-time   { color: #a5b4fc; font-size: 0.82em; font-weight: 500; white-space: nowrap; }
.sched-dur    { color: #9ca3af; font-size: 0.78em; white-space: nowrap; }

/* Day subheader */
.day-header {
    background: linear-gradient(90deg, rgba(102,126,234,0.2), transparent);
    border-left: 4px solid #667eea; border-radius: 0 10px 10px 0;
    padding: 10px 16px; margin: 20px 0 12px;
    animation: fadeInUp 0.3s ease-out;
}
.day-header .day-name  { color: #a5b4fc; font-weight: 700; font-size: 1em; }
.day-header .day-date  { color: #6b7280; font-size: 0.82em; margin-top: 2px; }
.day-today .day-name   { color: #34d399 !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(102,126,234,0.1), rgba(118,75,162,0.08)) !important;
    border: 1px solid rgba(102,126,234,0.2) !important;
    border-radius: 14px !important;
    padding: 16px !important;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; }
[data-testid="stMetricLabel"] { color: #6b7280 !important; }

/* Expander */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(102,126,234,0.2) !important;
    border-radius: 14px !important;
}

/* Buttons */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(102,126,234,0.3) !important;
}

/* Divider */
hr { border-color: rgba(102,126,234,0.2) !important; }

/* Dataframe */
[data-testid="stDataFrame"] {
    border-radius: 14px !important;
    overflow: hidden;
    border: 1px solid rgba(102,126,234,0.2) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>🐾 PawPal+</h1>
  <p>Your intelligent pet care scheduling companion — keep every paw on schedule.</p>
</div>
""", unsafe_allow_html=True)

# ── 1. Owner ────────────────────────────────────────────────────────────────
st.markdown('<div class="step-badge">👤 Step 1 — Owner</div>', unsafe_allow_html=True)

with st.expander("➕ Add a new owner", expanded=not owner_names()):
    col1, col2 = st.columns([3, 1])
    with col1:
        new_owner = st.text_input("Owner name", placeholder="e.g. Alice", label_visibility="collapsed")
    with col2:
        if st.button("Add owner", use_container_width=True):
            if new_owner.strip() and new_owner not in st.session_state.db["owners"]:
                st.session_state.db["owners"][new_owner] = {"pets": [], "weekly_availability": {}}
                _save()
                st.success(f"Owner '{new_owner}' added.")
                st.rerun()
            elif not new_owner.strip():
                st.warning("Enter a name first.")
            else:
                st.warning(f"'{new_owner}' already exists.")

if not owner_names():
    st.info("No owners yet — add one above to get started.")
    st.stop()

selected_owner: str = st.selectbox("Select owner", owner_names())
if not selected_owner or selected_owner not in st.session_state.db["owners"]:
    st.stop()

owner_data = st.session_state.db["owners"][selected_owner]
pet_count = len(owner_data.get("pets", []))

col_a, col_b = st.columns(2)
col_a.metric("Owner", selected_owner)
col_b.metric("Pets registered", pet_count)

# ── 2. Weekly Availability ───────────────────────────────────────────────────
st.divider()
st.markdown('<div class="step-badge">📅 Step 2 — Weekly Availability</div>', unsafe_allow_html=True)
st.write(
    f"Set **{selected_owner}'s** recurring weekly schedule. "
    "Tasks will only be assigned on available days, starting from the listed time."
)

weekly_stored = owner_data.get("weekly_availability", {})
new_weekly: dict = {}

SCHEDULE_MODES = ["🌅 All Day", "🕐 Custom Hours", "💼 Work Schedule", "🚫 Off"]

def _day_mode_from_cfg(cfg: dict) -> str:
    if not cfg.get("available", True):
        return "🚫 Off"
    if cfg.get("all_day", True):
        return "🌅 All Day"
    if cfg.get("has_busy_block", False):
        return "💼 Work Schedule"
    return "🕐 Custom Hours"

MODE_COLORS = {
    "🌅 All Day":       ("#34d399", "rgba(52,211,153,0.12)"),
    "🕐 Custom Hours":  ("#a5b4fc", "rgba(102,126,234,0.12)"),
    "💼 Work Schedule": ("#fbbf24", "rgba(251,191,36,0.12)"),
    "🚫 Off":           ("#6b7280", "rgba(107,114,128,0.08)"),
}

# ── Quick Templates ──────────────────────────────────────────────────────────
st.markdown(
    '<div style="color:#a5b4fc;font-weight:700;font-size:0.8em;letter-spacing:0.08em;'
    'margin-bottom:10px">⚡ QUICK TEMPLATES</div>',
    unsafe_allow_html=True,
)
TEMPLATES = {
    "🏢 Work Week": {
        d: ({"available": True, "all_day": False, "start": "07:00", "end": "22:00",
              "has_busy_block": True, "busy_start": "09:00", "busy_end": "17:00"}
            if d not in ("Saturday", "Sunday") else {"available": False})
        for d in DAYS_OF_WEEK
    },
    "🌈 Every Day": {
        d: {"available": True, "all_day": True, "start": "00:00", "end": "23:59",
            "has_busy_block": False, "busy_start": "08:00", "busy_end": "17:00"}
        for d in DAYS_OF_WEEK
    },
    "🏖️ Weekends Only": {
        d: ({"available": True, "all_day": True, "start": "00:00", "end": "23:59",
              "has_busy_block": False, "busy_start": "08:00", "busy_end": "17:00"}
            if d in ("Saturday", "Sunday") else {"available": False})
        for d in DAYS_OF_WEEK
    },
    "🌙 Evenings Only": {
        d: {"available": True, "all_day": False, "start": "17:00", "end": "22:00",
            "has_busy_block": False, "busy_start": "09:00", "busy_end": "17:00"}
        for d in DAYS_OF_WEEK
    },
}
t1, t2, t3, t4 = st.columns(4)
for col, (tname, tdata) in zip([t1, t2, t3, t4], TEMPLATES.items()):
    with col:
        if st.button(tname, use_container_width=True, key=f"tpl_{tname}_{selected_owner}"):
            owner_data["weekly_availability"] = tdata
            _save()
            st.rerun()

st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

# ── Bulk Apply ───────────────────────────────────────────────────────────────
with st.expander("📋 Apply same schedule to multiple days at once", expanded=False):
    st.markdown(
        '<div style="color:#9ca3af;font-size:0.82em;margin-bottom:12px">'
        'Select any days that share the same schedule, set the type below, and hit Apply.</div>',
        unsafe_allow_html=True,
    )
    ba1, ba2 = st.columns([3, 2])
    with ba1:
        bulk_days = st.multiselect(
            "Days to update", DAYS_OF_WEEK,
            placeholder="Pick days…", key=f"bulk_days_{selected_owner}",
        )
    with ba2:
        bulk_mode = st.selectbox(
            "Schedule type", SCHEDULE_MODES, key=f"bulk_mode_{selected_owner}",
        )

    bulk_start_str, bulk_end_str = "07:00", "22:00"
    bulk_has_busy, bulk_busy_start_str, bulk_busy_end_str = False, "09:00", "17:00"

    if bulk_mode == "🕐 Custom Hours":
        bh1, bh2 = st.columns(2)
        with bh1:
            bval = st.time_input("Available from", value=_parse_time("07:00"),
                                 key=f"bulk_start_{selected_owner}")
            bulk_start_str = bval.strftime("%H:%M")
        with bh2:
            bval2 = st.time_input("Available until", value=_parse_time("22:00"),
                                  key=f"bulk_end_{selected_owner}")
            bulk_end_str = bval2.strftime("%H:%M")

    elif bulk_mode == "💼 Work Schedule":
        bh1, bh2 = st.columns(2)
        with bh1:
            bval = st.time_input("Day starts", value=_parse_time("07:00"),
                                 key=f"bulk_dstart_{selected_owner}")
            bulk_start_str = bval.strftime("%H:%M")
        with bh2:
            bval2 = st.time_input("Day ends", value=_parse_time("22:00"),
                                  key=f"bulk_dend_{selected_owner}")
            bulk_end_str = bval2.strftime("%H:%M")
        bh3, bh4 = st.columns(2)
        bulk_has_busy = True
        with bh3:
            bval3 = st.time_input("Work hours from", value=_parse_time("09:00"),
                                  key=f"bulk_bstart_{selected_owner}")
            bulk_busy_start_str = bval3.strftime("%H:%M")
        with bh4:
            bval4 = st.time_input("Work hours until", value=_parse_time("17:00"),
                                  key=f"bulk_bend_{selected_owner}")
            bulk_busy_end_str = bval4.strftime("%H:%M")

    if st.button("✅ Apply to selected days", use_container_width=True,
                 disabled=not bulk_days, key=f"bulk_apply_{selected_owner}"):
        for bd in bulk_days:
            if bulk_mode == "🌅 All Day":
                owner_data["weekly_availability"][bd] = {
                    "available": True, "all_day": True, "start": "00:00", "end": "23:59",
                    "has_busy_block": False, "busy_start": "08:00", "busy_end": "17:00",
                }
            elif bulk_mode == "🚫 Off":
                owner_data["weekly_availability"][bd] = {"available": False}
            else:
                owner_data["weekly_availability"][bd] = {
                    "available": True, "all_day": False,
                    "start": bulk_start_str, "end": bulk_end_str,
                    "has_busy_block": bulk_has_busy,
                    "busy_start": bulk_busy_start_str, "busy_end": bulk_busy_end_str,
                }
        _save()
        st.success(f"Schedule applied to: {', '.join(bulk_days)}")
        st.rerun()

# ── Day Cards: Weekdays ───────────────────────────────────────────────────────
st.markdown(
    '<div style="background:linear-gradient(90deg,rgba(102,126,234,0.18),transparent);'
    'border-left:3px solid #667eea;border-radius:0 10px 10px 0;'
    'padding:9px 16px;margin:18px 0 12px">'
    '<span style="color:#a5b4fc;font-weight:700;font-size:0.82em;letter-spacing:0.07em">'
    '📅 WEEKDAYS — Mon to Fri</span></div>',
    unsafe_allow_html=True,
)
day_modes: dict[str, str] = {}
wd_cols = st.columns(5)
for i, day in enumerate(DAYS_OF_WEEK[:5]):
    day_cfg = weekly_stored.get(day, {"available": True, "all_day": True})
    stored_mode = _day_mode_from_cfg(day_cfg)
    with wd_cols[i]:
        mode = st.selectbox(
            day, SCHEDULE_MODES,
            index=SCHEDULE_MODES.index(stored_mode),
            key=f"mode_{day}_{selected_owner}",
        )
        day_modes[day] = mode
        m_accent, m_bg = MODE_COLORS[mode]
        is_on = mode != "🚫 Off"
        st.markdown(
            f'<div style="background:{m_bg};border:1px solid {m_accent}55;border-radius:8px;'
            f'padding:5px 8px;text-align:center;font-size:0.7em;color:{m_accent};'
            f'font-weight:700;margin-top:4px">{"🟢 Active" if is_on else "🔴 Off"}</div>',
            unsafe_allow_html=True,
        )

# ── Day Cards: Weekend ────────────────────────────────────────────────────────
st.markdown(
    '<div style="background:linear-gradient(90deg,rgba(251,191,36,0.18),transparent);'
    'border-left:3px solid #fbbf24;border-radius:0 10px 10px 0;'
    'padding:9px 16px;margin:18px 0 12px">'
    '<span style="color:#fbbf24;font-weight:700;font-size:0.82em;letter-spacing:0.07em">'
    '🏖️ WEEKEND — Sat & Sun</span></div>',
    unsafe_allow_html=True,
)
we1, we2, we_spacer = st.columns([2, 2, 6])
for col, day in zip([we1, we2], DAYS_OF_WEEK[5:]):
    day_cfg = weekly_stored.get(day, {"available": True, "all_day": True})
    stored_mode = _day_mode_from_cfg(day_cfg)
    with col:
        mode = st.selectbox(
            day, SCHEDULE_MODES,
            index=SCHEDULE_MODES.index(stored_mode),
            key=f"mode_{day}_{selected_owner}",
        )
        day_modes[day] = mode
        m_accent, m_bg = MODE_COLORS[mode]
        is_on = mode != "🚫 Off"
        st.markdown(
            f'<div style="background:{m_bg};border:1px solid {m_accent}55;border-radius:8px;'
            f'padding:5px 8px;text-align:center;font-size:0.7em;color:{m_accent};'
            f'font-weight:700;margin-top:4px">{"🟢 Active" if is_on else "🔴 Off"}</div>',
            unsafe_allow_html=True,
        )

# ── Time Configuration (only for days that need it) ──────────────────────────
needs_config = [d for d in DAYS_OF_WEEK if day_modes.get(d) in ("🕐 Custom Hours", "💼 Work Schedule")]
if needs_config:
    st.markdown(
        '<div style="color:#9ca3af;font-size:0.8em;font-weight:700;margin:18px 0 10px;'
        'letter-spacing:0.07em">⚙️ TIME CONFIGURATION</div>',
        unsafe_allow_html=True,
    )
    for day in needs_config:
        mode = day_modes[day]
        day_cfg = weekly_stored.get(day, {})
        stored_start      = _parse_time(day_cfg.get("start",      "07:00"))
        stored_end        = _parse_time(day_cfg.get("end",        "22:00"))
        stored_busy_start = _parse_time(day_cfg.get("busy_start", "09:00"))
        stored_busy_end   = _parse_time(day_cfg.get("busy_end",   "17:00"))
        m_accent, _ = MODE_COLORS[mode]

        with st.expander(f"{mode}  ·  {day}", expanded=True):
            if mode == "🕐 Custom Hours":
                dh1, dh2, dh3 = st.columns([2, 2, 6])
                with dh1:
                    start = st.time_input("From", value=stored_start,
                                          key=f"start_{day}_{selected_owner}")
                with dh2:
                    end = st.time_input("Until", value=stored_end,
                                        key=f"end_{day}_{selected_owner}")
                st.caption(f"{day}: {start.strftime('%H:%M')} → {end.strftime('%H:%M')}")

            elif mode == "💼 Work Schedule":
                st.markdown(
                    '<div style="color:#9ca3af;font-size:0.78em;margin-bottom:8px">'
                    'Set your day window and your busy (work) hours. '
                    'Pet tasks will be scheduled in the free slots around work.</div>',
                    unsafe_allow_html=True,
                )
                dh1, dh2 = st.columns(2)
                with dh1:
                    start = st.time_input("Day starts", value=stored_start,
                                          key=f"start_{day}_{selected_owner}")
                with dh2:
                    end = st.time_input("Day ends", value=stored_end,
                                        key=f"end_{day}_{selected_owner}")
                st.markdown(
                    '<div style="color:#fbbf24;font-size:0.78em;font-weight:600;margin:8px 0 4px">'
                    '💼 Busy / Work Window</div>',
                    unsafe_allow_html=True,
                )
                dh3, dh4 = st.columns(2)
                with dh3:
                    busy_start = st.time_input("Work from", value=stored_busy_start,
                                               key=f"busystart_{day}_{selected_owner}")
                with dh4:
                    busy_end = st.time_input("Work until", value=stored_busy_end,
                                             key=f"busyend_{day}_{selected_owner}")
                bs = start.strftime("%H:%M"); be = end.strftime("%H:%M")
                bbs = busy_start.strftime("%H:%M"); bbe = busy_end.strftime("%H:%M")
                st.caption(f"{day}: free {bs}–{bbs}  +  {bbe}–{be}  |  busy {bbs}–{bbe}")

# ── Build new_weekly from widget state ────────────────────────────────────────
for day in DAYS_OF_WEEK:
    mode = day_modes.get(day, "🌅 All Day")
    if mode == "🚫 Off":
        new_weekly[day] = {"available": False}
    elif mode == "🌅 All Day":
        new_weekly[day] = {
            "available": True, "all_day": True,
            "start": "00:00", "end": "23:59",
            "has_busy_block": False, "busy_start": "08:00", "busy_end": "17:00",
        }
    elif mode == "🕐 Custom Hours":
        s = st.session_state.get(f"start_{day}_{selected_owner}",    _parse_time("07:00"))
        e = st.session_state.get(f"end_{day}_{selected_owner}",      _parse_time("22:00"))
        new_weekly[day] = {
            "available": True, "all_day": False,
            "start": s.strftime("%H:%M"), "end": e.strftime("%H:%M"),
            "has_busy_block": False, "busy_start": "09:00", "busy_end": "17:00",
        }
    elif mode == "💼 Work Schedule":
        s  = st.session_state.get(f"start_{day}_{selected_owner}",     _parse_time("07:00"))
        e  = st.session_state.get(f"end_{day}_{selected_owner}",       _parse_time("22:00"))
        bs = st.session_state.get(f"busystart_{day}_{selected_owner}", _parse_time("09:00"))
        be = st.session_state.get(f"busyend_{day}_{selected_owner}",   _parse_time("17:00"))
        new_weekly[day] = {
            "available": True, "all_day": False,
            "start": s.strftime("%H:%M"), "end": e.strftime("%H:%M"),
            "has_busy_block": True,
            "busy_start": bs.strftime("%H:%M"), "busy_end": be.strftime("%H:%M"),
        }

if new_weekly != weekly_stored:
    owner_data["weekly_availability"] = new_weekly
    _save()

# ── Availability Summary ──────────────────────────────────────────────────────
avail_days   = [d for d in DAYS_OF_WEEK if new_weekly.get(d, {}).get("available", True)]
off_days     = [d for d in DAYS_OF_WEEK if not new_weekly.get(d, {}).get("available", True)]
workday_days = [d for d in avail_days if new_weekly.get(d, {}).get("has_busy_block")]

if not avail_days:
    st.warning("No available days set — the schedule will be empty.")
else:
    sm1, sm2, sm3 = st.columns(3)
    sm1.metric("Active days", len(avail_days))
    sm2.metric("Days off", len(off_days))
    sm3.metric("Work-schedule days", len(workday_days))
    st.success(f"Available: {', '.join(avail_days)}"
               + (f"  |  Off: {', '.join(off_days)}" if off_days else ""))

# ── 3. Pets ──────────────────────────────────────────────────────────────────
st.divider()
st.markdown(f'<div class="step-badge">🐾 Step 3 — Pets for {selected_owner}</div>', unsafe_allow_html=True)

with st.expander("➕ Add a new pet", expanded=pet_count == 0):
    with st.form("add_pet_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        with c1:
            pet_name = st.text_input("Pet name", placeholder="e.g. Buddy")
        with c2:
            species = st.selectbox("Species", ["dog", "cat", "bird", "rabbit", "fish", "other"])
        with c3:
            age = st.number_input("Age (yrs)", min_value=0, max_value=30, value=1)
        with c4:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("Add pet", use_container_width=True)

        if submitted:
            if not pet_name.strip():
                st.warning("Enter a pet name.")
            elif pet_name in pet_names(selected_owner):
                st.warning(f"'{pet_name}' already exists for {selected_owner}.")
            else:
                owner_data["pets"].append(
                    {"name": pet_name, "species": species, "age": int(age), "tasks": []}
                )
                _save()
                st.success(f"Pet '{pet_name}' added.")
                st.rerun()

pets = owner_data.get("pets", [])
if not pets:
    st.info("No pets yet — add one above.")
    st.stop()

cols = st.columns(min(len(pets), 4))
for i, p in enumerate(pets):
    emoji = SPECIES_EMOJI.get(p["species"], "🐾")
    task_count = len(p.get("tasks", []))
    with cols[i % 4]:
        st.markdown(
            f"""
            <div class="pet-card">
                <span class="emoji">{emoji}</span>
                <div class="name">{p['name']}</div>
                <div class="meta">{p['species'].capitalize()} · {p['age']} yr{'s' if p['age'] != 1 else ''}</div>
                <div class="badges">
                  <span class="badge">🗒 {task_count} task{'s' if task_count != 1 else ''}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── 4. Tasks ──────────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="step-badge">📋 Step 4 — Tasks</div>', unsafe_allow_html=True)

pet_names_list = [p["name"] for p in pets]
selected_pet_name = st.selectbox("Select pet", pet_names_list)
if selected_pet_name is None:
    st.stop()

selected_pet_data = next(p for p in pets if p["name"] == selected_pet_name)
species_emoji = SPECIES_EMOJI.get(selected_pet_data["species"], "🐾")

st.markdown(
    f"**{species_emoji} {selected_pet_name}** — "
    f"{selected_pet_data['species'].capitalize()}, {selected_pet_data['age']} yrs"
)

with st.form("add_task_form", clear_on_submit=True):
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        task_name = st.text_input("Task name", placeholder="e.g. Morning walk")
    with c2:
        duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
    with c3:
        priority = st.selectbox("Priority", ["high", "medium", "low"])

    c4, c5, c6 = st.columns([2, 2, 1])
    with c4:
        freq_choice = st.selectbox("Frequency", ["daily", "weekly", "monthly"])
    with c5:
        repeat_count = st.number_input(
            "Times per day / per week",
            min_value=1, max_value=20, value=1,
            help="For daily: how many times per day. For weekly: how many times per week. Ignored for monthly.",
        )
    with c6:
        st.write("")
        st.write("")
        add_task = st.form_submit_button("Add", use_container_width=True)

    if add_task:
        if not task_name.strip():
            st.warning("Enter a task name.")
        else:
            selected_pet_data["tasks"].append({
                "name": task_name,
                "duration": int(duration),
                "priority": priority,
                "frequency": freq_choice,
                "times_per_day": int(repeat_count) if freq_choice == "daily" else 1,
                "times_per_week": int(repeat_count) if freq_choice == "weekly" else 1,
            })
            _save()
            st.success(f"Task '{task_name}' added.")
            st.rerun()

all_tasks = [(p["name"], p["species"], t) for p in pets for t in p.get("tasks", [])]

if all_tasks:
    today_str = date.today().isoformat()

    st.markdown("**All tasks**")
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        filter_pet = st.multiselect(
            "Filter by pet", [p["name"] for p in pets],
            placeholder="All pets", key="task_filter_pet",
        )
    with cf2:
        sort_by = st.selectbox(
            "Sort by", ["Priority", "Duration ↑", "Duration ↓", "Name"],
            key="task_sort",
        )
    with cf3:
        filter_status = st.selectbox(
            "Status", ["All", "Not done today", "Done today"],
            key="task_filter_status",
        )

    visible = all_tasks
    if filter_pet:
        visible = [(pn, sp, t) for pn, sp, t in visible if pn in filter_pet]
    if filter_status == "Done today":
        visible = [(pn, sp, t) for pn, sp, t in visible
                   if _is_complete(selected_owner, pn, t["name"], today_str)]
    elif filter_status == "Not done today":
        visible = [(pn, sp, t) for pn, sp, t in visible
                   if not _is_complete(selected_owner, pn, t["name"], today_str)]

    if sort_by == "Duration ↑":
        visible.sort(key=lambda x: x[2]["duration"])
    elif sort_by == "Duration ↓":
        visible.sort(key=lambda x: x[2]["duration"], reverse=True)
    elif sort_by == "Name":
        visible.sort(key=lambda x: x[2]["name"].lower())
    else:
        visible.sort(key=lambda x: PRIORITY_ORDER.get(x[2]["priority"], 3))

    if not visible:
        st.warning("No tasks match the current filters.")
    else:
        done_count = sum(
            1 for pn, sp, t in visible
            if _is_complete(selected_owner, pn, t["name"], today_str)
        )
        total_count = len(visible)
        if done_count == total_count:
            st.success(f"All {total_count} tasks completed today!")
        elif done_count > 0:
            st.info(f"{done_count} of {total_count} tasks completed today.")

        # Styled priority cards
        PRIORITY_CARD_CLASS = {"high": "task-high", "medium": "task-medium", "low": "task-low"}
        PRIORITY_BADGE_CLASS = {"high": "priority-badge-high", "medium": "priority-badge-medium", "low": "priority-badge-low"}
        PRIORITY_LABEL = {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}

        for pet_name, species, t in visible:
            emoji = SPECIES_EMOJI.get(species, "🐾")
            freq_label = t["frequency"]
            if t["frequency"] == "daily" and t.get("times_per_day", 1) > 1:
                freq_label = f"daily × {t['times_per_day']}/day"
            elif t["frequency"] == "weekly" and t.get("times_per_week", 1) > 1:
                freq_label = f"weekly × {t['times_per_week']}/week"
            is_done = _is_complete(selected_owner, pet_name, t["name"], today_str)
            card_cls = PRIORITY_CARD_CLASS.get(t["priority"], "task-low")
            done_cls = " task-done" if is_done else ""
            badge_cls = PRIORITY_BADGE_CLASS.get(t["priority"], "priority-badge-low")
            priority_badge = PRIORITY_LABEL.get(t["priority"], t["priority"])
            name_html = f"<s>{t['name']}</s>" if is_done else t["name"]
            st.markdown(
                f"""<div class="task-card {card_cls}{done_cls}">
                  <span style="font-size:1.6em">{emoji}</span>
                  <div style="flex:1">
                    <div class="task-name">{name_html}</div>
                    <div class="task-meta">{pet_name} · ⏱ {t['duration']} min</div>
                  </div>
                  <span class="task-pill">{freq_label}</span>
                  <span class="{badge_cls}">{priority_badge}</span>
                  {'<span style="color:#34d399;font-size:1.2em" title="Done today">✓</span>' if is_done else ''}
                </div>""",
                unsafe_allow_html=True,
            )

        # Summary table via st.dataframe
        st.markdown("**Summary table**")
        table_data = [
            {
                "Pet": f"{SPECIES_EMOJI.get(sp, '🐾')} {pn}",
                "Task": t["name"],
                "Priority": t["priority"].capitalize(),
                "Duration (min)": t["duration"],
                "Frequency": (
                    f"daily × {t.get('times_per_day',1)}" if t["frequency"] == "daily" and t.get("times_per_day",1) > 1
                    else f"weekly × {t.get('times_per_week',1)}" if t["frequency"] == "weekly" and t.get("times_per_week",1) > 1
                    else t["frequency"].capitalize()
                ),
                "Done Today": "✅" if _is_complete(selected_owner, pn, t["name"], today_str) else "⬜",
            }
            for pn, sp, t in visible
        ]
        st.dataframe(table_data, use_container_width=True, hide_index=True)
else:
    st.info("No tasks yet — add one above.")

# ── 5. Schedule ───────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="step-badge">📆 Step 5 — Schedule</div>', unsafe_allow_html=True)

has_tasks = any(t for p in pets for t in p.get("tasks", []))
if not has_tasks:
    st.info("Add at least one task to a pet to generate a schedule.")
    st.stop()

tab_daily, tab_monthly = st.tabs(["📅 7-Day Daily Schedule", "🗓 Monthly Calendar"])

# ── Tab 1: Daily schedule ────────────────────────────────────────────────────
with tab_daily:
    st.write(f"Tasks for **{selected_owner}** over the next 7 days.")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        sched_filter_pet = st.multiselect(
            "Filter by pet", [p["name"] for p in pets],
            placeholder="All pets", key="sched_pet_filter",
        )
    with sc2:
        sched_sort = st.selectbox(
            "Sort by", ["Start Time", "Duration ↑", "Duration ↓", "Priority"],
            key="sched_sort",
        )
    with sc3:
        sched_status = st.selectbox(
            "Status", ["All", "Not done today", "Done today"],
            key="sched_status",
        )

    today = date.today()
    today_str = today.isoformat()
    any_day_shown = False

    for i in range(7):
        day = today + timedelta(days=i)
        if not _is_owner_available_on(selected_owner, day):
            continue
        entries = _tasks_due_on(pets, day, selected_owner)
        if not entries:
            continue

        # Pet filter
        if sched_filter_pet:
            entries = [(pn, sp, t) for pn, sp, t in entries if pn in sched_filter_pet]

        # Completion filter (only meaningful for today)
        if sched_status == "Done today" and i == 0:
            entries = [(pn, sp, t) for pn, sp, t in entries
                       if _is_complete(selected_owner, pn, t["name"], today_str)]
        elif sched_status == "Not done today" and i == 0:
            entries = [(pn, sp, t) for pn, sp, t in entries
                       if not _is_complete(selected_owner, pn, t["name"], today_str)]

        if not entries:
            continue

        any_day_shown = True
        day_name = day.strftime("%A")
        free_blocks = _owner_free_blocks(selected_owner, day_name)
        rows = _assign_times_with_meta(entries, free_blocks)

        # Sort
        if sched_sort == "Duration ↑":
            rows.sort(key=lambda r: r["_dur_raw"])
        elif sched_sort == "Duration ↓":
            rows.sort(key=lambda r: r["_dur_raw"], reverse=True)
        elif sched_sort == "Priority":
            rows.sort(key=lambda r: PRIORITY_ORDER.get(r["_priority_raw"], 3))

        label = "Today" if i == 0 else ("Tomorrow" if i == 1 else day.strftime("%A"))
        today_cls = " day-today" if i == 0 else ""
        st.markdown(
            f'<div class="day-header{today_cls}">'
            f'<div class="day-name">{"📍 " if i == 0 else ""}{label}</div>'
            f'<div class="day-date">{day.strftime("%B %d, %Y")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Conflict detection ────────────────────────────────────────────────
        conflicts = _detect_conflicts(rows)
        if conflicts:
            # ── Summary banner ────────────────────────────────────────────────
            sev_counts = {"Major": 0, "Moderate": 0, "Minor": 0}
            for a, b in conflicts:
                ov = _block_minutes(max(a["_start_raw"], b["_start_raw"]),
                                    min(a["_end_raw"],   b["_end_raw"]))
                sev_counts[_conflict_severity(ov)[0]] += 1

            worst = "Major" if sev_counts["Major"] else ("Moderate" if sev_counts["Moderate"] else "Minor")
            banner_color = {"Major": "#dc3545", "Moderate": "#fd7e14", "Minor": "#ffc107"}[worst]
            badges = ""
            if sev_counts["Major"]:    badges += f"&nbsp;&nbsp;🔴 {sev_counts['Major']} major"
            if sev_counts["Moderate"]: badges += f"&nbsp;&nbsp;🟠 {sev_counts['Moderate']} moderate"
            if sev_counts["Minor"]:    badges += f"&nbsp;&nbsp;🟡 {sev_counts['Minor']} minor"

            st.markdown(
                f'<div style="background:{banner_color}18;border-left:4px solid {banner_color};'
                f'padding:10px 16px;border-radius:0 6px 6px 0;margin:8px 0">'
                f'<strong>⚠️ {len(conflicts)} scheduling conflict{"s" if len(conflicts)>1 else ""}</strong>'
                f'{badges}<br>'
                f'<small style="color:#666">These tasks overlap — use the options below to fix them.</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

            with st.expander("View & fix conflicts", expanded=(worst in ("Major", "Moderate"))):
                for idx, (a, b) in enumerate(conflicts):
                    overlap_start = max(a["_start_raw"], b["_start_raw"])
                    overlap_end   = min(a["_end_raw"],   b["_end_raw"])
                    overlap_min   = _block_minutes(overlap_start, overlap_end)
                    sev_label, sev_emoji, sev_color = _conflict_severity(overlap_min)

                    # Which task to suggest shortening (lower priority → shorten it)
                    if _priority_rank(a["_priority_raw"]) > _priority_rank(b["_priority_raw"]):
                        suggest, keep = a, b
                    else:
                        suggest, keep = b, a

                    # ── Conflict card ─────────────────────────────────────────
                    st.markdown(
                        f'<div style="border:1px solid {sev_color}55;border-radius:8px;'
                        f'padding:14px 16px;margin-bottom:4px;background:{sev_color}08">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center">'
                        f'<strong style="font-size:1em">Conflict {idx + 1} of {len(conflicts)}</strong>'
                        f'<span style="background:{sev_color};color:white;padding:2px 10px;'
                        f'border-radius:12px;font-size:0.78em">{sev_emoji} {sev_label} — {overlap_min} min overlap</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                    # Task detail rows
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        st.markdown(
                            f"**{a['Pet']}** &nbsp;·&nbsp; {a['Task']}\n\n"
                            f"<small>⏱ {a['Start']} – {a['End']}&nbsp;&nbsp;{a['Priority']}</small>",
                            unsafe_allow_html=True,
                        )
                    with cc2:
                        st.markdown(
                            f"**{b['Pet']}** &nbsp;·&nbsp; {b['Task']}\n\n"
                            f"<small>⏱ {b['Start']} – {b['End']}&nbsp;&nbsp;{b['Priority']}</small>",
                            unsafe_allow_html=True,
                        )

                    # Timeline bar
                    if free_blocks:
                        st.markdown(
                            _render_conflict_timeline_html(a, b, free_blocks[0][0], free_blocks[-1][1]),
                            unsafe_allow_html=True,
                        )

                    # Priority-aware suggestion
                    st.info(
                        f"💡 **Suggestion:** Shorten **{suggest['_task_raw']}** by {overlap_min} min "
                        f"— it has lower priority than {keep['_task_raw']}."
                    )

                    # Action buttons
                    fa1, fa2, fa3 = st.columns([2, 2, 2])

                    auto_key = f"autofix_{day}_{idx}_{a['_pet_raw']}_{a['_task_raw']}"
                    with fa1:
                        if st.button(
                            f"⚡ Auto-fix: shorten {suggest['_task_raw'][:14]}",
                            key=auto_key, type="primary", use_container_width=True,
                        ):
                            pet_data = next((p for p in owner_data["pets"] if p["name"] == suggest["_pet_raw"]), None)
                            if pet_data:
                                task_rec = next((t for t in pet_data["tasks"] if t["name"] == suggest["_task_raw"]), None)
                                if task_rec:
                                    task_rec["duration"] = max(1, suggest["_dur_raw"] - overlap_min)
                                    _save()
                                    st.success(f"✓ {suggest['_task_raw']} → {task_rec['duration']} min")
                                    st.rerun()

                    fix_key_a = f"cfix_{day}_{idx}_{a['_pet_raw']}_{a['_task_raw']}"
                    fix_key_b = f"cfix_{day}_{idx}_{b['_pet_raw']}_{b['_task_raw']}"
                    with fa2:
                        new_dur_a = st.number_input(
                            f"Shorten **{a['_task_raw'][:16]}** (min)",
                            min_value=1, max_value=240,
                            value=max(1, a["_dur_raw"] - overlap_min),
                            key=fix_key_a,
                        )
                        if st.button(f"Apply to {a['_task_raw'][:14]}", key=fix_key_a + "_btn", use_container_width=True):
                            pet_data = next((p for p in owner_data["pets"] if p["name"] == a["_pet_raw"]), None)
                            if pet_data:
                                task_rec = next((t for t in pet_data["tasks"] if t["name"] == a["_task_raw"]), None)
                                if task_rec:
                                    task_rec["duration"] = int(new_dur_a)
                                    _save()
                                    st.rerun()
                    with fa3:
                        new_dur_b = st.number_input(
                            f"Shorten **{b['_task_raw'][:16]}** (min)",
                            min_value=1, max_value=240,
                            value=max(1, b["_dur_raw"] - overlap_min),
                            key=fix_key_b,
                        )
                        if st.button(f"Apply to {b['_task_raw'][:14]}", key=fix_key_b + "_btn", use_container_width=True):
                            pet_data = next((p for p in owner_data["pets"] if p["name"] == b["_pet_raw"]), None)
                            if pet_data:
                                task_rec = next((t for t in pet_data["tasks"] if t["name"] == b["_task_raw"]), None)
                                if task_rec:
                                    task_rec["duration"] = int(new_dur_b)
                                    _save()
                                    st.rerun()

                    if idx < len(conflicts) - 1:
                        st.divider()

        if i == 0:
            # Today — progress summary
            done_today = sum(
                1 for r in rows
                if _is_complete(selected_owner, r["_pet_raw"], r["_task_raw"], today_str)
            )
            if done_today == len(rows) and len(rows) > 0:
                st.success(f"All {len(rows)} tasks for today are done! Great job!")
            elif done_today > 0:
                st.info(f"Progress: {done_today}/{len(rows)} tasks completed today.")

            SCHED_CARD_CLASS = {"high": "sched-high", "medium": "sched-medium", "low": "sched-low"}
            for r in rows:
                pet_raw = r["_pet_raw"]
                task_raw = r["_task_raw"]
                is_done = _is_complete(selected_owner, pet_raw, task_raw, today_str)
                occ_label = r["Occurrence"]
                card_cls = SCHED_CARD_CLASS.get(r["_priority_raw"], "sched-low")
                done_cls = " sched-done" if is_done else ""
                dur_or_occ = occ_label if occ_label != "—" else r["Duration"]
                name_html = f"<s>{task_raw}</s>" if is_done else task_raw
                st.markdown(
                    f'<div class="sched-card {card_cls}{done_cls}">'
                    f'<div style="flex:1"><div class="sched-name">{r["Pet"]} — {name_html}</div>'
                    f'<div style="color:#6b7280;font-size:0.78em">{dur_or_occ} · {r["Priority"]}</div></div>'
                    f'<div class="sched-time">⏱ {r["Start"]} → {r["End"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                btn_key = f"sched_done_{today_str}_{pet_raw}_{task_raw}_{occ_label}"
                col_btn, _ = st.columns([1, 5])
                with col_btn:
                    if st.button(
                        "✓ Done" if is_done else "Mark done",
                        key=btn_key,
                        use_container_width=True,
                        type="secondary" if is_done else "primary",
                    ):
                        _toggle_complete(selected_owner, pet_raw, task_raw, today_str)
                        st.rerun()
        else:
            # Future days — use st.dataframe for a clean professional look
            display_rows = [
                {
                    "Pet": r["Pet"],
                    "Task": r["Task"],
                    "Start": r["Start"],
                    "End": r["End"],
                    "Duration": r["Duration"],
                    "Priority": r["Priority"],
                    "Occurrence": r["Occurrence"],
                }
                for r in rows
            ]
            st.dataframe(display_rows, use_container_width=True, hide_index=True)

    if not any_day_shown:
        st.info("No tasks match the current filters for the next 7 days.")

# ── Tab 2: Monthly calendar ──────────────────────────────────────────────────
with tab_monthly:
    today = date.today()
    col_prev, col_label, col_next = st.columns([1, 4, 1])

    if "cal_year" not in st.session_state:
        st.session_state.cal_year = today.year
    if "cal_month" not in st.session_state:
        st.session_state.cal_month = today.month

    with col_prev:
        if st.button("◀", use_container_width=True):
            m = st.session_state.cal_month - 1
            if m < 1:
                m = 12
                st.session_state.cal_year -= 1
            st.session_state.cal_month = m
    with col_next:
        if st.button("▶", use_container_width=True):
            m = st.session_state.cal_month + 1
            if m > 12:
                m = 1
                st.session_state.cal_year += 1
            st.session_state.cal_month = m

    cal_year = st.session_state.cal_year
    cal_month = st.session_state.cal_month

    task_map = _build_month_task_map(selected_owner, cal_year, cal_month)
    st.markdown(_render_calendar_html(cal_year, cal_month, task_map), unsafe_allow_html=True)

    # Legend
    st.markdown("---")
    st.caption("🔴 High priority &nbsp;&nbsp; 🟡 Medium priority &nbsp;&nbsp; 🟢 Low priority &nbsp;&nbsp; 🟩 Today")

    # Click-to-expand: show full task list for a day in the month
    days_with_tasks = sorted(task_map.keys())
    if days_with_tasks:
        st.write("**View tasks for a specific day:**")
        selected_day = st.selectbox(
            "Pick a day",
            options=days_with_tasks,
            format_func=lambda d: d.strftime("%A, %B %d"),
            label_visibility="collapsed",
        )
        if selected_day:
            entries = task_map[selected_day]
            day_name = selected_day.strftime("%A")
            free_blocks = _owner_free_blocks(selected_owner, day_name)
            rows = _assign_times(entries, free_blocks)
            if rows:
                high_count = sum(1 for r in rows if "high" in r.get("Priority", "").lower())
                if high_count:
                    st.warning(f"{high_count} high-priority task{'s' if high_count > 1 else ''} scheduled for this day.")
                else:
                    st.success(f"{len(rows)} task{'s' if len(rows) > 1 else ''} scheduled — no high-priority conflicts.")
                st.dataframe(rows, use_container_width=True, hide_index=True)

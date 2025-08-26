from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Set
import zoneinfo

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes, CallbackContext, MessageHandler, CommandHandler, filters,
)

# ============ CONFIG ============
TIMEZONE = zoneinfo.ZoneInfo("Asia/Kolkata")  # IST

# Academic day boundaries & lunch
EARLY_OPEN = time(9, 0, tzinfo=TIMEZONE)     # NEW: we treat 9:00–9:30 as “pre-class window”
COLLEGE_OPEN = time(9, 30, tzinfo=TIMEZONE)
COLLEGE_CLOSE = time(17, 30, tzinfo=TIMEZONE)
LUNCH_FROM = time(13, 30, tzinfo=TIMEZONE)
LUNCH_TO = time(14, 30, tzinfo=TIMEZONE)

# Canonical 1-hour slots (7 per day)
SLOTS: List[Tuple[time, time]] = [
    (time(9, 30, tzinfo=TIMEZONE), time(10, 30, tzinfo=TIMEZONE)),
    (time(10, 30, tzinfo=TIMEZONE), time(11, 30, tzinfo=TIMEZONE)),
    (time(11, 30, tzinfo=TIMEZONE), time(12, 30, tzinfo=TIMEZONE)),
    (time(12, 30, tzinfo=TIMEZONE), time(13, 30, tzinfo=TIMEZONE)),
    (time(14, 30, tzinfo=TIMEZONE), time(15, 30, tzinfo=TIMEZONE)),
    (time(15, 30, tzinfo=TIMEZONE), time(16, 30, tzinfo=TIMEZONE)),
    (time(16, 30, tzinfo=TIMEZONE), time(17, 30, tzinfo=TIMEZONE)),
]

@dataclass
class ClassEntry:
    subject: str
    room: str
    teacher: Optional[str] = None

# -----------------------------
# WEEK SCHEDULE (7 slots/day)
# -----------------------------
# IMPORTANT: each day MUST have EXACTLY 7 entries (None allowed).
# I normalized your table to 7 slots / day and placed labs into proper 2–3 slot spans where relevant.
SCHEDULE: Dict[int, List[Optional[ClassEntry]]] = {
    0: [  # MON
        ClassEntry("DMDW", "BS-102"),
        ClassEntry("OS", "BS-102"),
        ClassEntry("AIML", "BS-102"),
        ClassEntry("WT", "BS-102"),
        ClassEntry("DMDW LAB", "MBA Gallary"),
        ClassEntry("DMDW LAB", "MBA Gallary"),
        ClassEntry("DMDW LAB", "MBA Gallary"),
    ],
    1: [  # TUE
        ClassEntry("OS", "BS-104"),
        ClassEntry("WT LAB", "BS-104"),
        ClassEntry("WT LAB", "BS-104"),
        ClassEntry("WT LAB", "BS-104"),
        ClassEntry("DMDW", "CS-201"),
        ClassEntry("AIML", "CS-201"),
        ClassEntry("AIML", "CS-201"),
    ],
    2: [  # WED
        ClassEntry("SDE", "Chutti"),
        ClassEntry("SDE", "Chutti"),
        ClassEntry("SDE", "Chutti"),
        None,
        ClassEntry("CDT", "Chutti"),
        ClassEntry("CDT", "Chutti"),
        ClassEntry("CDT", "Chutti"),
    ],
    3: [  # THU
        ClassEntry("WT (Oracle Lab)", "Oracle Lab"),
        ClassEntry("WT", "Oracle Lab"),
        ClassEntry("AIML LAB", "Oracle Lab"),
        ClassEntry("AIML LAB", "Oracle Lab"),
        ClassEntry("AIML LAB", "Oracle Lab"),
        ClassEntry("DMDW", "BS-403"),
        ClassEntry("AIML", "BS-403"),
        ClassEntry("OS", "BS-403"),
    ],
    4: [  # FRI
        ClassEntry("DMDW", "CS-201"),
        ClassEntry("OS", "CS-201"),
        ClassEntry("WT", "CS-201"),
        ClassEntry("WT", "CS-201"),
        ClassEntry("OS LAB", "MECH DC"),
        ClassEntry("OS LAB", "MECH DC"),
        ClassEntry("OS LAB", "MECH DC"),
    ],
    5: [None, None, None, None, None, None, None],  # SAT (co-curricular only)
    6: [None, None, None, None, None, None, None],  # SUN closed
}

SUPPORTED_GROUPS = {"Group-7": SCHEDULE}

FACULTY = {
    "AIML": "Dr. Priya Rao (CSE)",
    "WT": "Subhrasmita Gouda (CSE)",
    "OS": "Dr. Ashish Ranjan (CSIT)",
    "DMDW": "Dr. Bichitrananda Behera (CSE)",
}

DEVELOPER_TEXT = (
    "Developer: @Moltentungsten (Yash Kumar Raut)\n"
    "Timetable: CVRGU, Group-7, Sem-5.\n"
    "Dept. Coordinator: Dr. B.N. Behera;\n"
    "University Coordinator: Dr. G. Mohanta."
)

# ===== Admins (fill with your Telegram numeric user IDs) =====
ADMIN_IDS: Set[int] = {
    1255061320
}

# Track chats we can broadcast to (users or groups that interacted)
KNOWN_CHATS: Set[int] = set()

# ================= Utilities =================
def ist_now() -> datetime:
    return datetime.now(TIMEZONE)

def slot_index_for(now: Optional[datetime] = None) -> Optional[int]:
    """Return the index of the current slot, or None if we're between slots/lunch/before first/after last."""
    now = now or ist_now()
    for i, (start, end) in enumerate(SLOTS):
        if start <= now.timetz() < end:
            return i
    return None

def _day_slot_start(dt: datetime, slot_idx: int) -> datetime:
    return datetime.combine(dt.date(), SLOTS[slot_idx][0]).replace(tzinfo=TIMEZONE)

def next_class(group: str, now: Optional[datetime] = None) -> Optional[Tuple[datetime, ClassEntry]]:
    """
    Robust next-class finder:
    - Works during lunch or between slots.
    - Scans from 'now' forward (today then upcoming days).
    """
    now = now or ist_now()
    schedule = SUPPORTED_GROUPS.get(group)
    if not schedule:
        return None

    for dshift in range(0, 7):
        day_idx = (now.weekday() + dshift) % 7
        base_date = now.date() + timedelta(days=dshift)
        for i in range(len(SLOTS)):
            start_dt = datetime.combine(base_date, SLOTS[i][0]).replace(tzinfo=TIMEZONE)
            if dshift == 0 and start_dt <= now:
                continue
            entry = schedule[day_idx][i]
            if entry:
                return start_dt, entry
    return None

def current_class(group: str, now: Optional[datetime] = None) -> Optional[ClassEntry]:
    now = now or ist_now()
    idx = slot_index_for(now)
    if idx is None:
        return None
    schedule = SUPPORTED_GROUPS.get(group)
    if not schedule:
        return None
    return schedule[now.weekday()][idx]

def format_entry(entry: ClassEntry) -> str:
    sub_key = entry.subject.split()[0]
    teacher = FACULTY.get(sub_key)
    t_str = f"\nFaculty: {teacher}" if teacher else ""
    return f"{entry.subject} @ {entry.room}{t_str}"

def day_schedule(group: str, day_idx: int) -> str:
    """Pretty list with a lunch line inserted after the 4th slot."""
    lines = []
    for i, (start, end) in enumerate(SLOTS):
        entry = SUPPORTED_GROUPS[group][day_idx][i]
        label = f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
        if entry:
            lines.append(f"{label}: {format_entry(entry)}")
        else:
            lines.append(f"{label}: —")
        if i == 3:  # after 12:30–13:30 slot
            lines.append("13:30–14:30: Lunch Break")
    return "\n".join(lines)

# ================= Persistence =================
USER_GROUP: Dict[int, str] = {}

# ================= UI & Handlers =================
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("Where is the class?"), KeyboardButton("Who is the developer?")]],
    resize_keyboard=True,
)

async def _remember_chat(update: Update):
    chat_id = update.effective_chat.id
    KNOWN_CHATS.add(chat_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    user = update.effective_user
    if user and user.id not in USER_GROUP:
        USER_GROUP[user.id] = "Group-7"
    await update.message.reply_text(
        "Welcome! You are registered under Group-7.\n"
        "Use the buttons below or commands:\n"
        "/today • /next • /subscribe • /announce (admin) • /tomorrow • /week • /setgroup • /help",
        reply_markup=MAIN_KEYBOARD
    )

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    if not context.args:
        await update.message.reply_text("Usage: /setgroup Group-7")
        return
    group = " ".join(context.args)
    if group not in SUPPORTED_GROUPS:
        await update.message.reply_text(f"Unknown group '{group}'. Supported: {', '.join(SUPPORTED_GROUPS.keys())}")
        return
    USER_GROUP[update.effective_user.id] = group
    await update.message.reply_text(f"Updated your group to {group}.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    await update.message.reply_text(
        "/start – register & menu\n"
        "/today – today's schedule\n"
        "/next – next class from now\n"
        "/subscribe – 10-min reminders before each remaining class today\n"
        "/tomorrow – tomorrow's schedule\n"
        "/week – week at a glance\n"
        "/announce <msg> – admin broadcast\n"
        "/setgroup <name> – change your group\n"
        "/help – this help"
    )

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    text = (update.message.text or "").strip().lower()
    if "where is the class" in text:
        await where_is_class(update, context)
    elif "who is the developer" in text:
        await update.message.reply_text(DEVELOPER_TEXT)
    else:
        await update.message.reply_text("Please use the provided buttons or /help.")

async def where_is_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    user_id = update.effective_user.id
    group = USER_GROUP.get(user_id, "Group-7")
    now = ist_now()
    wk = now.weekday()

    # Sunday: closed, but offer next class
    if wk == 6:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            await update.message.reply_text(f"Sunday: No classes.\nNext class {when.strftime('%a %H:%M')} – {format_entry(entry)}")
        else:
            await update.message.reply_text("Sunday: No classes.")
        return

    # Before first slot (including 09:00–09:30): do not say closed; show first class instead
    first_start = SLOTS[0][0]
    if now.timetz() < first_start:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            await update.message.reply_text(f"First class {when.strftime('%H:%M')} – {format_entry(entry)}")
        else:
            await update.message.reply_text("No classes found today.")
        return

    # Lunch window message + show next class
    if LUNCH_FROM <= now.timetz() < LUNCH_TO:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            await update.message.reply_text(f"It's lunch (13:30–14:30).\nNext class {when.strftime('%H:%M')} – {format_entry(entry)}")
        else:
            await update.message.reply_text("It's lunch (13:30–14:30). No more classes today.")
        return

    # After last slot: tell next day’s first class
    if now.timetz() >= SLOTS[-1][1]:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            await update.message.reply_text(f"No more classes today.\nNext class {when.strftime('%a %H:%M')} – {format_entry(entry)}")
        else:
            await update.message.reply_text("No more classes today.")
        return

    # Within slot or between slots: try current, else next
    cur = current_class(group, now)
    if cur:
        idx = slot_index_for(now)
        start, end = SLOTS[idx]
        await update.message.reply_text(f"Current ({start.strftime('%H:%M')}–{end.strftime('%H:%M')}):\n{format_entry(cur)}")
    else:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            await update.message.reply_text(f"Next class {when.strftime('%H:%M')} – {format_entry(entry)}")
        else:
            await update.message.reply_text("No class right now.")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    d = ist_now().weekday()
    await update.message.reply_text(f"Today's schedule for {group}:\n" + day_schedule(group, d))

async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    d = (ist_now().weekday() + 1) % 7
    await update.message.reply_text(f"Tomorrow's schedule for {group}:\n" + day_schedule(group, d))

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    msg = []
    for d in range(7):
        label = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d]
        msg.append(f"\n*{label}*")
        msg.append(day_schedule(group, d))
    await update.message.reply_text("\n".join(msg))

async def next_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    nxt = next_class(group, ist_now())
    if not nxt:
        await update.message.reply_text("No upcoming classes found.")
        return
    when, entry = nxt
    await update.message.reply_text(f"Next class at {when.strftime('%a %H:%M')} – {format_entry(entry)}")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedules one-off reminders 10 minutes before each remaining class today (robust across lunch & gaps)."""
    await _remember_chat(update)
    user_id = update.effective_user.id
    group = USER_GROUP.get(user_id, "Group-7")
    now = ist_now()
    day = now.weekday()
    jobs = 0
    for i, (start, _end) in enumerate(SLOTS):
        slot_time = datetime.combine(now.date(), start).replace(tzinfo=TIMEZONE)
        if slot_time <= now:
            continue
        entry = SUPPORTED_GROUPS[group][day][i]
        if not entry:
            continue
        remind_at = slot_time - timedelta(minutes=10)
        if remind_at <= now:
            continue
        context.job_queue.run_once(
            reminder_job,
            when=remind_at,
            data={"chat_id": update.effective_chat.id, "entry": entry, "slot": (start.strftime('%H:%M'))},
            name=f"reminder-{user_id}-{slot_time.isoformat()}",
            chat_id=update.effective_chat.id,
        )
        jobs += 1
    if jobs:
        await update.message.reply_text(f"Subscribed: I'll remind you 10 minutes before {jobs} class(es) today.")
    else:
        await update.message.reply_text("No remaining classes to remind you about today.")

async def reminder_job(context: CallbackContext):
    data = context.job.data
    entry: ClassEntry = data["entry"]
    slot_label = data["slot"]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"⏰ Reminder ({slot_label}): {format_entry(entry)}",
    )

# ------------- Admin Broadcast -------------
async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: /announce <message> — broadcasts to all known chats."""
    await _remember_chat(update)
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not allowed to use /announce.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /announce <message>")
        return
    text = " ".join(context.args)
    sent = 0
    for chat_id in list(KNOWN_CHATS):
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"📣 {text}")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"Announcement sent to {sent} chat(s).")

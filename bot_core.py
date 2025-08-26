from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Set
import zoneinfo

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, CallbackContext, MessageHandler, CommandHandler, filters,
)

# ============ CONFIG ============
TIMEZONE = zoneinfo.ZoneInfo("Asia/Kolkata")  # IST

# Academic day boundaries & lunch
EARLY_OPEN = time(9, 0, tzinfo=TIMEZONE)     # treat 9:00–9:30 as pre-class window
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
# Each day MUST have exactly 7 entries (None allowed).
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
    "*Developer:* @Moltentungsten (Yash Kumar Raut)\n"
    "Timetable: CVRGU, Group-7, Sem-5.\n"
    "Dept. Coordinator: Dr. B.N. Behera.\n"
    "University Coordinator: Dr. G. Mohanta."
)

# ===== Admins (fill with your Telegram numeric user IDs) =====
ADMIN_IDS: Set[int] = {1255061320}

# Track chats we can broadcast to (users or groups that interacted)
KNOWN_CHATS: Set[int] = set()

# ================ Pretty helpers ================
def ist_now() -> datetime:
    return datetime.now(TIMEZONE)

def slot_index_for(now: Optional[datetime] = None) -> Optional[int]:
    now = now or ist_now()
    for i, (start, end) in enumerate(SLOTS):
        if start <= now.timetz() < end:
            return i
    return None

def pretty_slot_label(start: time, end: time) -> str:
    return f"🕒 *{start.strftime('%H:%M')}–{end.strftime('%H:%M')}*"

def pretty_entry(entry: ClassEntry) -> str:
    sub_key = entry.subject.split()[0]
    teacher = FACULTY.get(sub_key)
    t = f"\n    👨‍🏫 {teacher}" if teacher else ""
    return f"📘 {entry.subject} @ {entry.room}{t}"

def day_schedule(group: str, day_idx: int) -> str:
    """Return a nicely formatted schedule for a day (with a lunch line)."""
    parts: List[str] = []
    for i, (start, end) in enumerate(SLOTS):
        entry = SUPPORTED_GROUPS[group][day_idx][i]
        if entry:
            parts.append(f"{pretty_slot_label(start, end)}\n{pretty_entry(entry)}")
        else:
            parts.append(f"{pretty_slot_label(start, end)}\n— Free —")
        if i == 3:
            parts.append("🍴 *13:30–14:30: Lunch Break*")
    return "\n\n".join(parts)

def current_class(group: str, now: Optional[datetime] = None) -> Optional[ClassEntry]:
    now = now or ist_now()
    idx = slot_index_for(now)
    if idx is None:
        return None
    schedule = SUPPORTED_GROUPS.get(group)
    if not schedule:
        return None
    return schedule[now.weekday()][idx]

def next_class(group: str, now: Optional[datetime] = None) -> Optional[Tuple[datetime, ClassEntry]]:
    """Robust next-class finder across lunch, gaps, and day rolls."""
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

# ================= Persistence =================
USER_GROUP: Dict[int, str] = {}

# ================= UI & Handlers =================
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("Where is the class?"), KeyboardButton("Who is the developer?")]],
    resize_keyboard=True,
)

async def _remember_chat(update: Update):
    KNOWN_CHATS.add(update.effective_chat.id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    user = update.effective_user
    if user and user.id not in USER_GROUP:
        USER_GROUP[user.id] = "Group-7"
    text = (
        "*Welcome!* You are registered under *Group-7*.\n\n"
        "• /today – today’s timetable\n"
        "• /next – next class from now\n"
        "• /subscribe – reminders 10 min before each class today\n"
        "• /tomorrow – tomorrow’s timetable\n"
        "• /week – week at a glance\n"
        "• /setgroup <name> – change group\n"
        "• /announce <msg> – admin broadcast\n"
        "• /help – command list"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD, parse_mode=ParseMode.MARKDOWN)

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    if not context.args:
        await update.message.reply_text("*Usage:* /setgroup Group-7", parse_mode=ParseMode.MARKDOWN)
        return
    group = " ".join(context.args)
    if group not in SUPPORTED_GROUPS:
        await update.message.reply_text(
            f"Unknown group '{group}'. Supported: {', '.join(SUPPORTED_GROUPS.keys())}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    USER_GROUP[update.effective_user.id] = group
    await update.message.reply_text(f"Updated your group to *{group}*.", parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    text = (
        "*Commands*\n\n"
        "• /today – today’s timetable\n"
        "• /next – next class from now\n"
        "• /subscribe – reminders 10 min before each class today\n"
        "• /tomorrow – tomorrow’s timetable\n"
        "• /week – week at a glance\n"
        "• /announce <msg> – admin broadcast\n"
        "• /setgroup <name> – change your group\n"
        "• /help – this help"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    text = (update.message.text or "").strip().lower()
    if "where is the class" in text:
        await where_is_class(update, context)
    elif "who is the developer" in text:
        await update.message.reply_text(DEVELOPER_TEXT, parse_mode=ParseMode.MARKDOWN)
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
            msg = f"Sunday: No classes.\n\n*Next:* {when.strftime('%a %H:%M')}\n{pretty_entry(entry)}"
        else:
            msg = "Sunday: No classes."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    # Before first slot (incl. 09:00–09:30): don’t say closed; show first class
    first_start = SLOTS[0][0]
    if now.timetz() < first_start:
        when, entry = next_class(group, now)
        msg = f"*First class {when.strftime('%H:%M')}*\n{pretty_entry(entry)}"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    # Lunch window → show next class
    if LUNCH_FROM <= now.timetz() < LUNCH_TO:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            msg = f"🍴 *Lunch (13:30–14:30)*\n\n*Next {when.strftime('%H:%M')}*\n{pretty_entry(entry)}"
        else:
            msg = "🍴 *Lunch (13:30–14:30)*\n\nNo more classes today."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    # After last slot → next day
    if now.timetz() >= SLOTS[-1][1]:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            msg = f"No more classes today.\n\n*Next:* {when.strftime('%a %H:%M')}\n{pretty_entry(entry)}"
        else:
            msg = "No more classes today."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    # Within slot or between slots
    cur = current_class(group, now)
    if cur:
        idx = slot_index_for(now)
        start, end = SLOTS[idx]
        msg = f"*Current* {pretty_slot_label(start, end)}\n{pretty_entry(cur)}"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    else:
        nxt = next_class(group, now)
        if nxt:
            when, entry = nxt
            msg = f"*Next {when.strftime('%H:%M')}*\n{pretty_entry(entry)}"
        else:
            msg = "No class right now."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    d = ist_now().weekday()
    text = f"*Today’s schedule for {group}:*\n\n" + day_schedule(group, d)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    d = (ist_now().weekday() + 1) % 7
    text = f"*Tomorrow’s schedule for {group}:*\n\n" + day_schedule(group, d)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    labels = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    parts: List[str] = []
    for d in range(7):
        parts.append(f"*{labels[d]}*")
        parts.append(day_schedule(group, d))
        if d < 6:
            parts.append("")  # extra blank line between days
    await update.message.reply_text("\n".join(parts), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def next_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _remember_chat(update)
    group = USER_GROUP.get(update.effective_user.id, "Group-7")
    nxt = next_class(group, ist_now())
    if not nxt:
        await update.message.reply_text("No upcoming classes found.")
        return
    when, entry = nxt
    msg = f"*Next class* {when.strftime('%a %H:%M')}\n{pretty_entry(entry)}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedules one-off reminders 10 minutes before each remaining class today."""
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
        await update.message.reply_text(
            f"✅ Subscribed: I’ll remind you *10 minutes before* {jobs} class(es) today.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("No remaining classes to remind you about today.")

async def reminder_job(context: CallbackContext):
    data = context.job.data
    entry: ClassEntry = data["entry"]
    slot_label = data["slot"]
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"⏰ *Reminder* ({slot_label})\n{pretty_entry(entry)}",
        parse_mode=ParseMode.MARKDOWN,
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



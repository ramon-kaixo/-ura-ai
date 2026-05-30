#!/usr/bin/env python3
"""
Apple Integration — FASE 7
───────────────────────────
Calendar, Reminders, Notes vía AppleScript.
URA puede leer/crear eventos, recordatorios y notas.
"""

import subprocess
from datetime import datetime, timedelta


def run_applescript(script: str) -> str:
    """Ejecuta AppleScript y devuelve el resultado."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


# ── Calendar ────────────────────────────────────────────────


def get_calendar_events(days: int = 7) -> list[dict]:
    """Lee los próximos eventos del calendario."""
    script = f"""
    tell application "Calendar"
        set out to ""
        set startDate to (current date)
        set endDate to (current date) + {days} * days
        repeat with cal in calendars
            set eventList to (events of cal whose start date >= startDate and start date <= endDate)
            repeat with ev in eventList
                set out to out & (summary of ev) & "|" & (start date of ev) & "|" & (name of cal) & "||"
            end repeat
        end repeat
        return out
    end tell
    """
    raw = run_applescript(script)
    events = []
    for line in raw.split("||"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            events.append(
                {
                    "title": parts[0].strip(),
                    "date": parts[1].strip(),
                    "calendar": parts[2].strip(),
                }
            )
    return events


def create_calendar_event(
    title: str, date_str: str = "", duration_min: int = 60, calendar_name: str = "Calendar"
) -> bool:
    """Crea un evento en el calendario."""
    if not date_str:
        date = datetime.now() + timedelta(hours=1)
        date_str = date.strftime("%Y-%m-%d %H:%M:%S")

    script = f"""
    tell application "Calendar"
        tell calendar "{calendar_name}"
            set newEvent to make new event with properties {{summary:"{title}", start date:date "{date_str}", end date:(date "{date_str}") + {duration_min} * minutes}}
        end tell
    end tell
    """
    try:
        run_applescript(script)
        return True
    except RuntimeError:
        return False


# ── Reminders ───────────────────────────────────────────────


def get_reminders(list_name: str = "") -> list[dict]:
    """Lee los recordatorios pendientes."""
    list_filter = f'whose name is "{list_name}"' if list_name else ""

    script = f"""
    tell application "Reminders"
        set out to ""
        repeat with lst in lists {list_filter}
            repeat with rem in (reminders of lst whose completed is false)
                set out to out & (name of rem) & "|" & (name of lst) & "|" & (due date of rem) & "||"
            end repeat
        end repeat
        return out
    end tell
    """
    raw = run_applescript(script)
    reminders = []
    for line in raw.split("||"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            reminders.append(
                {
                    "title": parts[0].strip(),
                    "list": parts[1].strip() if len(parts) > 1 else "",
                    "due": parts[2].strip() if len(parts) > 2 else "",
                }
            )
    return reminders


def create_reminder(title: str, list_name: str = "Reminders") -> bool:
    """Crea un recordatorio."""
    script = f"""
    tell application "Reminders"
        set lst to list "{list_name}"
        make new reminder at lst with properties {{name:"{title}"}}
    end tell
    """
    try:
        run_applescript(script)
        return True
    except RuntimeError:
        return False


# ── Notes ───────────────────────────────────────────────────


def get_notes(search: str = "", max_notes: int = 10) -> list[dict]:
    """Lee notas de Notes.app."""
    search_clause = f'whose name contains "{search}" or body contains "{search}"' if search else ""

    script = f"""
    tell application "Notes"
        set out to ""
        repeat with n in (notes {search_clause})
            if (count of out) < {max_notes * 5000} then
                set out to out & (name of n) & "|" & (body of n) & "||"
            end if
            if (count of (get notes)) > {max_notes} then exit repeat
        end repeat
        return out
    end tell
    """
    raw = run_applescript(script)
    notes = []
    for line in raw.split("||"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 1)
        if len(parts) >= 2:
            notes.append(
                {
                    "title": parts[0].strip(),
                    "body": parts[1].strip()[:500],
                }
            )
    return notes


def create_note(title: str, body: str = "") -> bool:
    """Crea una nota en Notes.app."""
    safe_body = body.replace('"', '\\"').replace("\n", "\\n")
    script = f"""
    tell application "Notes"
        make new note with properties {{name:"{title}", body:"{safe_body}"}}
    end tell
    """
    try:
        run_applescript(script)
        return True
    except RuntimeError:
        return False


# ── Prueba ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("📅 Calendario:")
    for ev in get_calendar_events(7)[:5]:
        print(f"  {ev['date'][:16]} | {ev['title']}")

    print("\n📝 Recordatorios:")
    for rem in get_reminders()[:5]:
        print(f"  [{rem['list']}] {rem['title']}")

    print("\n📒 Notas recientes:")
    for note in get_notes(max_notes=3):
        print(f"  {note['title']}")

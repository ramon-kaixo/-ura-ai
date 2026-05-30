#!/usr/bin/env python3
"""
Integración con aplicaciones Apple de URA - Nivel 22

URA interactúa con aplicaciones nativas de macOS:
- Calendar: leer eventos del día y crear nuevos eventos
- Reminders: leer recordatorios pendientes y añadir nuevos
- Notes: leer notas existentes y crear notas nuevas
"""

import logging
import subprocess
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Evento de calendario."""

    title: str
    start_date: str
    end_date: str
    location: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Reminder:
    """Recordatorio."""

    title: str
    due_date: str
    completed: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Note:
    """Nota."""

    title: str
    body: str
    created_date: str
    folder: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class AppleIntegration:
    """Integración con aplicaciones Apple."""

    def __init__(self):
        self._check_availability()

    def _check_availability(self):
        """Verifica que AppleScript esté disponible."""
        try:
            subprocess.run(["osascript", "-e", 'return "ok"'], capture_output=True, timeout=5)
            logger.info("AppleScript disponible")
        except Exception as e:
            logger.warning(f"AppleScript no disponible: {e}")

    def _run_applescript(self, script: str) -> str:
        """Ejecuta un script de AppleScript y devuelve la salida."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("Timeout ejecutando AppleScript")
            return ""
        except Exception as e:
            logger.error(f"Error ejecutando AppleScript: {e}")
            return ""

    # Calendar
    def get_today_events(self) -> list[CalendarEvent]:
        """Obtiene eventos del calendario de hoy."""
        script = """
        tell application "Calendar"
            tell calendar "Home"
                set today to current date
                set time of today to 0
                set tomorrow to today + (1 * days)
                set todayEvents to every event whose start date is greater than or equal to today and start date is less than tomorrow
                set eventList to ""
                repeat with evt in todayEvents
                    set eventList to eventList & (summary of evt) & "|" & (start date of evt as string) & "|" & (end date of evt as string) & "\\n"
                end repeat
                return eventList
            end tell
        end tell
        """

        output = self._run_applescript(script)
        events = []

        for line in output.split("\\n"):
            if line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    events.append(
                        CalendarEvent(title=parts[0], start_date=parts[1], end_date=parts[2])
                    )

        return events

    def create_event(self, event: CalendarEvent) -> bool:
        """Crea un nuevo evento en el calendario."""
        script = f"""
        tell application "Calendar"
            tell calendar "Home"
                set newEvent to make new event at end with properties {{summary:"{event.title}", start date:date "{event.start_date}", end date:date "{event.end_date}"}}
                if "{event.location}" is not "" then set location of newEvent to "{event.location}"
                if "{event.notes}" is not "" then set notes of newEvent to "{event.notes}"
            end tell
        end tell
        """

        output = self._run_applescript(script)
        return len(output) > 0 or output == ""

    # Reminders
    def get_pending_reminders(self) -> list[Reminder]:
        """Obtiene recordatorios pendientes."""
        script = """
        tell application "Reminders"
            set reminderList to ""
            tell list "Personal"
                set pendingReminders to every reminder whose completed is false
                repeat with rem in pendingReminders
                    set reminderList to reminderList & (name of rem) & "|" & (due date of rem as string) & "\\n"
                end repeat
            end tell
            return reminderList
        end tell
        """

        output = self._run_applescript(script)
        reminders = []

        for line in output.split("\\n"):
            if line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    reminders.append(Reminder(title=parts[0], due_date=parts[1], completed=False))

        return reminders

    def create_reminder(self, reminder: Reminder) -> bool:
        """Crea un nuevo recordatorio."""
        script = f"""
        tell application "Reminders"
            tell list "Personal"
                set newReminder to make new reminder with properties {{name:"{reminder.title}", due date:date "{reminder.due_date}"}}
                if "{reminder.notes}" is not "" then set notes of newReminder to "{reminder.notes}"
            end tell
        end tell
        """

        output = self._run_applescript(script)
        return len(output) > 0 or output == ""

    # Notes
    def get_notes(self, folder: str = "") -> list[Note]:
        """Obtiene notas existentes."""
        script = """
        tell application "Notes"
            set noteList to ""
            tell account "iCloud"
                set allNotes to every note
                repeat with n in allNotes
                    set noteList to noteList & (name of n) & "|" & (body of n) & "|" & (creation date of n as string) & "\\n"
                end repeat
            end tell
            return noteList
        end tell
        """

        output = self._run_applescript(script)
        notes = []

        for line in output.split("\\n"):
            if line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    notes.append(
                        Note(title=parts[0], body=parts[1], created_date=parts[2], folder=folder)
                    )

        return notes

    def create_note(self, note: Note) -> bool:
        """Crea una nueva nota."""
        script = f"""
        tell application "Notes"
            tell account "iCloud"
                set newNote to make new note at end with properties {{name:"{note.title}", body:"{note.body}"}}
            end tell
        end tell
        """

        output = self._run_applescript(script)
        return len(output) > 0 or output == ""

    def get_today_summary(self) -> dict:
        """Obtiene un resumen del día: eventos y recordatorios."""
        events = self.get_today_events()
        reminders = self.get_pending_reminders()

        return {
            "events": [e.to_dict() for e in events],
            "reminders": [r.to_dict() for r in reminders],
            "event_count": len(events),
            "reminder_count": len(reminders),
        }


# Singleton
_apple_integration: AppleIntegration | None = None


def get_apple_integration() -> AppleIntegration:
    """Obtener el singleton de integración con Apple."""
    global _apple_integration
    if _apple_integration is None:
        _apple_integration = AppleIntegration()
    return _apple_integration


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    integration = get_apple_integration()

    print("Integración con Apple creada")
    summary = integration.get_today_summary()
    print(f"Eventos hoy: {summary['event_count']}")
    print(f"Recordatorios pendientes: {summary['reminder_count']}")

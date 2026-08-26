from dataclasses import dataclass
from enum import Enum


class Command(str, Enum):
    create_task = "create_task"
    list_tasks = "list_tasks"
    complete_task = "complete_task"
    read_recent_email = "read_recent_email"
    open_app = "open_app"
    create_reminder = "create_reminder"
    schedule_event = "schedule_event"
    summarize_today = "summarize_today"
    what_was_i_doing = "what_was_i_doing"
    send_message = "send_message"


@dataclass
class StructuredCommand:
    command: str
    title: str = ""
    details: str = ""
    time: str = ""

    def is_allowed_command(self) -> bool:
        return self.command in {item.value for item in Command}

    def is_complete_for_execution(self) -> bool:
        if self.command in {Command.create_task.value, Command.create_reminder.value, Command.schedule_event.value}:
            return bool((self.title or self.details or "").strip())
        if self.command == Command.open_app.value:
            return bool((self.title or self.details or "").strip())
        return True

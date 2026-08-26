import logging
import re

from structured_command import Command, StructuredCommand


logger = logging.getLogger(__name__)


def log_execution(*args, **kwargs):
    logger.info("voice_pipeline_execution", extra={"args": str(args), "kwargs": str(kwargs)})


def run_pipeline(text="", device="PC", execute_callback=None):
    command_text = str(text or "").strip()
    lower = command_text.lower()
    structured = _parse_command(lower, command_text)

    if not structured:
        return {
            "need_confirmation": False,
            "prompt": "",
            "structured_commands": [],
            "results": [],
        }

    results = execute_callback([structured], device) if execute_callback else []
    prompt = " ".join(item.get("result", "") for item in results if isinstance(item, dict)).strip()
    return {
        "need_confirmation": False,
        "prompt": prompt,
        "structured_commands": [structured],
        "results": results,
    }


def _parse_command(lower, original):
    if any(key in lower for key in ("list tasks", "show tasks", "my tasks")):
        return StructuredCommand(Command.list_tasks.value)
    if lower.startswith(("complete task", "finish task", "mark task")):
        title = re.sub(r"^(complete|finish|mark)\s+task\s*", "", original, flags=re.I).strip()
        return StructuredCommand(Command.complete_task.value, title=title)
    if lower.startswith(("create task", "add task", "new task")):
        title = re.sub(r"^(create|add|new)\s+task\s*", "", original, flags=re.I).strip()
        return StructuredCommand(Command.create_task.value, title=title, details=title)
    if "recent email" in lower or "latest email" in lower:
        return StructuredCommand(Command.read_recent_email.value)
    if lower.startswith(("open app", "launch app")):
        title = re.sub(r"^(open|launch)\s+app\s*", "", original, flags=re.I).strip()
        return StructuredCommand(Command.open_app.value, title=title)
    if lower.startswith(("set reminder", "create reminder", "add reminder", "remind me")):
        details = re.sub(r"^(set|create|add)\s+reminder\s*", "", original, flags=re.I).strip()
        details = re.sub(r"^remind me\s*", "", details, flags=re.I).strip()
        return StructuredCommand(Command.create_reminder.value, title=details, details=details)
    if lower.startswith(("schedule event", "create event", "add event")):
        details = re.sub(r"^(schedule|create|add)\s+event\s*", "", original, flags=re.I).strip()
        return StructuredCommand(Command.schedule_event.value, title=details, details=details)
    if "today schedule" in lower or "summarize today" in lower:
        return StructuredCommand(Command.summarize_today.value)
    if "what was i doing" in lower:
        return StructuredCommand(Command.what_was_i_doing.value)
    if lower.startswith(("send message", "message")):
        details = re.sub(r"^(send\s+message|message)\s*", "", original, flags=re.I).strip()
        return StructuredCommand(Command.send_message.value, title=details, details=details)
    return None

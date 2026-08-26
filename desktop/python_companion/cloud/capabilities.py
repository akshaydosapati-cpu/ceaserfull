from __future__ import annotations

import re
from typing import Any

from .backend_client import BackendError, CloudBackendClient


CLOUD_RESOURCE_PATTERN = re.compile(
    r"\b(my\s+(?:latest\s+)?(?:document|documents|file|files|report|reports|proposal)|ceaser\s+(?:cloud|document|documents|file|files|report|reports|proposal)|cloud|latest\s+(?:document|documents|file|files|report|reports|proposal)|document|documents|file|files|report|reports|proposal|upload|download|rename|restore|deleted|search my files|search files)\b",
    re.IGNORECASE,
)


def is_cloud_resource_command(command: str) -> bool:
    text = str(command or "")
    if re.search(r"^\s*(?:open|show|launch)\s+(?:(?:my|the)\s+)?(?:downloads|documents|desktop|pictures|videos|music|recycle\s*bin|file\s*explorer)\b", text, re.IGNORECASE):
        return False
    if re.search(r"^\s*(?:open|show|launch)\s+.+\s+in\s+(?:downloads|documents|desktop|file\s*explorer)\b", text, re.IGNORECASE):
        return False
    if not CLOUD_RESOURCE_PATTERN.search(text):
        return False
    # Creating or preparing content is an AI/document workflow unless the user
    # explicitly names CEASER cloud or asks to store/upload the result there.
    if re.search(r"\b(write|draft|prepare|generate)\b", text, re.IGNORECASE) and not re.search(
        r"\b(ceaser\s+cloud|cloud|upload|save|store)\b", text, re.IGNORECASE
    ):
        return False
    return bool(
        re.search(r"\b(latest|read|open|show|list|search|find|upload|download|delete|remove|restore|rename|update|create|save|store)\b", text, re.IGNORECASE)
        and re.search(r"\b(my|ceaser|cloud|latest|document|documents|file|files|report|reports|proposal|upload|download|restore)\b", text, re.IGNORECASE)
    )


def classify_cloud_action(command: str) -> str:
    lowered = str(command or "").lower()
    if re.search(r"\b(delete|remove)\b", lowered):
        return "delete"
    if "restore" in lowered:
        return "restore"
    if "upload" in lowered:
        return "upload"
    if "download" in lowered:
        return "download"
    if re.search(r"\b(rename|update)\b", lowered):
        return "update"
    if re.search(r"\b(create|new)\b", lowered):
        return "create"
    if re.search(r"\b(search|find)\b", lowered):
        return "search"
    if "latest" in lowered:
        return "latest"
    if re.search(r"\b(read|open|show)\b", lowered):
        return "read"
    return "list"


def build_cloud_payload(command: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    lowered = str(command or "").lower()
    resource_type = "resource"
    if "document" in lowered:
        resource_type = "document"
    elif "report" in lowered:
        resource_type = "report"
    elif "proposal" in lowered:
        resource_type = "proposal"
    elif "file" in lowered:
        resource_type = "file"
    query = ""
    match = re.search(r"\b(?:for|about|named|called)\s+(.+)$", str(command or ""), re.IGNORECASE)
    if match:
        query = match.group(1).strip(" .")
    return {
        "command": command,
        "resource_type": resource_type,
        "query": query,
        "context": context or {},
    }


def execute_cloud_command(command: str, context: dict[str, Any] | None = None, client: CloudBackendClient | None = None) -> dict[str, Any] | None:
    if not is_cloud_resource_command(command):
        return None
    action = classify_cloud_action(command)
    payload = build_cloud_payload(command, context)
    backend = client or CloudBackendClient()
    try:
        response = backend.cloud_resource(action, payload)
        data = response.data or {}
        message = data.get("message") or data.get("summary") or _format_items(action, data.get("items") or data.get("results") or [])
        return {
            "status": data.get("status") or "completed",
            "message": message or "CEASER cloud completed the request.",
            "context_kind": "cloud",
            "cloud_action": action,
            "resource_type": payload["resource_type"],
            "latency_ms": response.latency_ms,
            "items": data.get("items") or data.get("results") or [],
            "evidence": {
                "backend_path": f"/desktop/cloud/{action}",
                "cache_status": response.cache_status,
                "backend_latency_ms": response.latency_ms,
            },
        }
    except BackendError as exc:
        status = "offline" if exc.category in {"offline", "timeout", "backend_unavailable", "network_error"} else "error"
        return {
            "status": status,
            "message": str(exc),
            "context_kind": "cloud",
            "cloud_action": action,
            "resource_type": payload["resource_type"],
            "error_code": exc.category,
            "retryable": exc.retryable,
        }


def _format_items(action: str, items: list[Any]) -> str:
    if not items:
        if action == "latest":
            return "I could not find a latest CEASER resource for this account."
        return "No CEASER cloud resources matched that request."
    lines = []
    for index, item in enumerate(items[:8], start=1):
        if isinstance(item, dict):
            name = item.get("title") or item.get("name") or item.get("filename") or item.get("id") or "Untitled"
            kind = item.get("type") or item.get("resource_type") or ""
            lines.append(f"{index}. {name}{f' - {kind}' if kind else ''}")
        else:
            lines.append(f"{index}. {item}")
    return "Here are the matching CEASER cloud resources:\n" + "\n".join(lines)

from __future__ import annotations

import re

from core.schemas import IntentResult
from routing.entity_extractor import EntityExtractor
from routing.phrase_normalizer import PhraseNormalizer


class IntentRouter:
    def __init__(self) -> None:
        self.phrases = PhraseNormalizer()
        self.entities = EntityExtractor()

    def resolve(self, command: str, context: dict | None = None) -> IntentResult:
        text = str(command or "").strip()
        lowered = self.phrases.normalize(text)
        context = context or {}
        if not text:
            return IntentResult(intent="empty", capability="unsupported", confidence=1.0, route="unsupported")

        references = context.get("references") or {}
        if references.get("follow_up_detected") and re.search(r"\b(continue|again|why|how|summarize|summarise|explain|brief|more|table|chart|list|checklist|make it)\b", lowered):
            return IntentResult(
                intent="follow_up",
                capability="ai.answer",
                confidence=0.82,
                route="backend_ai",
                entities={"resolved_reference": references.get("resolved_reference")},
            )

        if re.search(r"\b(stop talking|stop speaking|cancel speech|be quiet|silence)\b", lowered):
            return IntentResult(intent="cancel_speech", capability="desktop.media_play_pause", confidence=0.92, route="desktop")

        # Resolve browser objects before generic windows/applications. A tab or
        # page must never fall through to window.close/app.close.
        tab_entities = self.entities.extract(lowered)
        tab_close = bool(
            re.match(r"^close\b", lowered)
            and (
                re.search(r"\b(tab|page)\b", lowered)
                or tab_entities.get("object_type") == "browser_tab"
            )
        )
        if tab_close:
            return IntentResult(
                intent="close_browser_tab",
                capability="desktop.close_browser_tab",
                confidence=0.97,
                route="desktop",
                entities=tab_entities,
            )

        tab_action = re.match(r"^(?:switch to|go to|find)\s+(.+?)\s+(?:tab|page)$", lowered)
        if tab_action:
            entities = self.entities.extract(lowered)
            entities.setdefault("target", tab_action.group(1).strip())
            entities["object_type"] = "browser_tab"
            return IntentResult(intent="switch_browser_tab", capability="browser.tab.switch", confidence=0.92, route="desktop", entities=entities)

        if re.fullmatch(r"(?:next tab|previous tab)", lowered):
            direction = "next" if lowered.startswith("next") else "previous"
            return IntentResult(intent=f"browser_tab_{direction}", capability="browser.tab.switch", confidence=0.96, route="desktop", entities={"direction": direction, "object_type": "browser_tab"})

        if re.fullmatch(r"(?:refresh|reload)(?: (?:this|the|current))? (?:page|tab)", lowered):
            return IntentResult(intent="browser_refresh", capability="browser.reload", confidence=0.96, route="desktop")

        window_match = re.match(r"^\s*(minimize|maximize|restore|focus|bring)\s+(?:the\s+)?(.+?)(?:\s+window)?\s*$", lowered)
        if window_match:
            action, target = window_match.groups()
            action = "focus" if action == "bring" else action
            return IntentResult(intent=f"window_{action}", capability=f"window.{action}", confidence=0.94, route="desktop", entities={"target": target})

        close_window_match = re.match(r"^\s*close\s+(?:the\s+)?(.+?)\s+window\s*$", lowered)
        if close_window_match:
            return IntentResult(intent="window_close", capability="window.close", confidence=0.96, route="desktop", entities={"target": close_window_match.group(1).strip()})

        if re.fullmatch(r"\s*(show (?:the )?desktop|minimize all windows)\s*", lowered):
            return IntentResult(intent="show_desktop", capability="window.show_desktop", confidence=0.97, route="desktop")

        if re.match(r"^\s*(?:open|show)\s+(?:the\s+)?(?:windows\s+)?settings", lowered):
            page_match = re.search(r"\b(network|bluetooth|display|sound|apps|storage|power|privacy|windows update|update)\b", lowered)
            return IntentResult(intent="open_settings", capability="system.open_settings", confidence=0.96, route="desktop", entities={"page": page_match.group(1) if page_match else ""})

        power_match = re.fullmatch(r"\s*(lock|sleep|hibernate|shutdown|shut down|restart|reboot|sign out|log out)(?:\s+(?:my|the)\s+(?:computer|laptop|pc))?\s*", lowered)
        if power_match:
            action = {"shut down": "shutdown", "reboot": "restart", "log out": "sign_out", "sign out": "sign_out"}.get(power_match.group(1), power_match.group(1))
            return IntentResult(intent=f"system_{action}", capability=f"system.{action}", confidence=0.98, route="desktop")

        if re.fullmatch(r"\s*(?:list|show|which|what)(?:\s+which)?\s+(?:apps|applications|processes)(?:\s+are)?\s+(?:running|open)\??\s*", lowered):
            return IntentResult(intent="list_running_apps", capability="app.list_running", confidence=0.95, route="desktop")

        if re.match(r"^\s*(?:copy|write)\s+.+\s+to\s+(?:the\s+)?clipboard\s*$", lowered):
            text_value = re.sub(r"^\s*(?:copy|write)\s+|\s+to\s+(?:the\s+)?clipboard\s*$", "", text, flags=re.IGNORECASE)
            return IntentResult(intent="clipboard_write", capability="clipboard.write", confidence=0.94, route="desktop", entities={"text": text_value})
        if re.fullmatch(r"\s*(?:read|show|what(?:'s| is) in)\s+(?:the\s+)?clipboard\??\s*", lowered):
            return IntentResult(intent="clipboard_read", capability="clipboard.read", confidence=0.94, route="desktop")
        if re.fullmatch(r"\s*(?:clear|empty)\s+(?:the\s+)?clipboard\s*", lowered):
            return IntentResult(intent="clipboard_clear", capability="clipboard.clear", confidence=0.96, route="desktop")

        if re.search(
            r"^\s*(?:(?:what(?:'s| is)|show|tell me|check)\s+)?(?:my\s+)?(?:battery|charge|power)\s*(?:percentage|level|status)?\s*\??$",
            lowered,
        ):
            return IntentResult(intent="battery_status", capability="desktop.get_battery", confidence=0.94, route="desktop")

        if re.search(r"\b(weather|temperature|forecast)\b", lowered):
            return IntentResult(intent="weather_lookup", capability="ai.weather", confidence=0.94, route="desktop")

        file_match = re.match(r"^(?:find|show|where is|open)\s+(?:my\s+)?(.+?)(?:\s+file)?$", lowered)
        if file_match and re.search(r"\b(file|folder|pdf|docx?|pptx?|notes?|assignment|project)\b", lowered):
            target = file_match.group(1).strip()
            capability = "file.open" if lowered.startswith("open ") else "file.search"
            return IntentResult(intent="local_file_request", capability=capability, confidence=0.84, route="desktop", entities={"path": target, "query": target})

        if re.match(r"^\s*(search|look up|lookup|find|google|search google|google search)\b", lowered) and not re.search(r"\b(my files|files|folders|notes|memories|notion|github|repos?|repositories)\b", lowered):
            return IntentResult(intent="web_search", capability="desktop.open_url", confidence=0.9, route="desktop")

        if re.search(r"\b(news|headlines|latest updates|current updates)\b", lowered):
            return IntentResult(intent="news_lookup", capability="ai.news", confidence=0.86, route="backend_ai")

        open_match = re.match(
            r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+)?(?P<verb>open|launch|start|run|switch\s+to|focus)\s+(?P<target>.+?)\s*$",
            lowered,
            re.IGNORECASE,
        )
        if open_match:
            target = open_match.group("target").strip()
            verb = open_match.group("verb").lower()
            original_match = re.match(r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+)?(?:open|launch|start|run|switch\s+to|focus)\s+(.+?)\s*$", text, re.IGNORECASE)
            display_target = original_match.group(1).strip() if original_match else target
            execution_command = text if verb in {"switch to", "focus"} else f"open {display_target}"
            entities = {"target": target, "execution_command": execution_command}
            if re.search(r"\b(downloads|documents|desktop|folder)\b", lowered):
                return IntentResult(intent="open_folder", capability="desktop.open_folder", confidence=0.9, route="desktop", entities=entities)
            if re.search(r"\b(https?://|www\.|\.com|\.in|\.tech|website|site|facebook|youtube|gmail|github|google)\b", lowered):
                return IntentResult(intent="open_url", capability="desktop.open_url", confidence=0.92, route="desktop", entities=entities)
            return IntentResult(intent="open_application", capability="app.open", confidence=0.96, route="desktop", entities=entities)

        # Speech recognition can return natural verb-last phrasing such as
        # "Chrome open". Keep this generic so every discovered application
        # follows the same launcher path without language-specific phrase maps.
        verb_last_open = re.match(
            r"^\s*(?P<target>.+?)\s+(?:open|launch|start|run)(?:\s+please)?\s*$",
            lowered,
        )
        if verb_last_open:
            target = verb_last_open.group("target").strip()
            return IntentResult(
                intent="open_application",
                capability="app.open",
                confidence=0.92,
                route="desktop",
                entities={"target": target, "execution_command": f"open {target}"},
            )

        if re.fullmatch(r"\s*(close|quit|exit|terminate)\s*", lowered) or re.match(r"^\s*(close|quit|exit|terminate)\s+.+", lowered):
            if re.fullmatch(r"close (?:it|that)", lowered):
                resolved = (context.get("references") or {}).get("resolved_reference") or {}
                target = resolved.get("target") or resolved.get("application") or context.get("active_application")
                if not target:
                    return IntentResult(intent="close_ambiguous", capability="app.close", confidence=0.42, route="desktop", requires_clarification=True, clarification_question="Which application or browser tab should I close?")
                return IntentResult(intent="close_application", capability="app.close", confidence=0.86, route="desktop", entities={"target": str(target)})
            return IntentResult(intent="close_application", capability="app.close", confidence=0.88, route="desktop")

        if re.search(r"\b(take|capture|grab).*\b(screen\s*shot|screenshot|screen)\b|\bscreenshot\b", lowered):
            return IntentResult(intent="take_screenshot", capability="screen.capture_all", confidence=0.96, route="desktop")

        if re.fullmatch(r"\s*lock\s+(?:the\s+)?screen\s*", lowered):
            return IntentResult(intent="lock_screen", capability="system.lock", confidence=0.98, route="desktop")

        if re.search(r"\b(delete|remove)\b.*\b(file|folder|project|it|this|that)\b", lowered):
            return IntentResult(intent="delete_file", capability="desktop.delete_file", confidence=0.82, route="desktop")

        if re.search(r"\b(volume|sound|audio|louder|quieter)\b", lowered):
            level_match = re.search(r"\b(\d{1,3})\s*%?", lowered)
            capability = "audio.unmute" if "unmute" in lowered else "audio.mute" if "mute" in lowered else "audio.volume.up" if re.search(r"\b(up|increase|raise|louder|more)\b", lowered) else "audio.volume.down" if re.search(r"\b(down|decrease|lower|quieter|less)\b", lowered) else "audio.volume.set"
            return IntentResult(intent="set_volume", capability=capability, confidence=0.92, route="desktop", entities={"level": int(level_match.group(1)) if level_match else None, "step": 10})

        if re.search(r"\b(brightness|screen)\b", lowered) and re.search(r"\b(bright|dark|brightness|screen)\b", lowered):
            level_match = re.search(r"\b(\d{1,3})\s*%?", lowered)
            capability = "display.brightness.up" if re.search(r"\b(increase|raise|up|brighter|more|high)\b", lowered) else "display.brightness.down" if re.search(r"\b(decrease|lower|low|down|darker|less|reduce)\b", lowered) else "display.brightness.set" if level_match else "display.brightness.get"
            return IntentResult(intent="brightness_control", capability=capability, confidence=0.94, route="desktop", entities={"level": int(level_match.group(1)) if level_match else None, "step": 10})

        radio_match = re.fullmatch(
            r"\s*(?:(?:turn|switch)\s+(?:the\s+)?)?(wi-?fi|wireless|bluetooth)\s+(on|off)\s*"
            r"|\s*(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(wi-?fi|wireless|bluetooth)\s*"
            r"|\s*(enable|disable)\s+(?:the\s+)?(wi-?fi|wireless|bluetooth)\s*",
            lowered,
        )
        if radio_match:
            radio = radio_match.group(1) or radio_match.group(4) or radio_match.group(6)
            enabled = (
                radio_match.group(2) == "on"
                if radio_match.group(2)
                else radio_match.group(3) == "on"
                if radio_match.group(3)
                else radio_match.group(5) == "enable"
            )
            prefix = "wifi" if radio in {"wifi", "wi-fi", "wireless"} else "bluetooth"
            return IntentResult(intent=f"{prefix}_control", capability=f"{prefix}.{'enable' if enabled else 'disable'}", confidence=0.96, route="desktop")

        if re.search(
            r"^\s*(?:play|pause|resume|continue|stop|next|previous|skip|rewind|forward|backward)(?:\s+(?:the\s+)?(?:music|song|track|media|playback))?(?:\s+\d+\s*(?:seconds?|minutes?))?\s*$",
            lowered,
        ):
            first = re.match(r"^\s*(\w+)", lowered).group(1)
            action = {"pause": "pause", "play": "play", "resume": "play", "continue": "play", "stop": "stop", "next": "next", "skip": "next", "forward": "seek_forward", "previous": "previous", "rewind": "seek_backward", "backward": "seek_backward"}.get(first, "play_pause")
            entities = self.entities.extract(lowered)
            return IntentResult(intent="media_control", capability=f"media.{action}", confidence=0.9, route="desktop", entities=entities)

        if re.search(r"\b(increase|upgrade|add)\b.*\b(ram|memory hardware|storage hardware)\b", lowered):
            return IntentResult(intent="unsupported_physical_upgrade", capability="unsupported", confidence=0.98, route="unsupported", entities={"unsupported_category": "physical_upgrade"})
        if re.search(r"\b(send|message)\b.*\bwhatsapp\b", lowered):
            return IntentResult(intent="unsupported_whatsapp_send", capability="unsupported", confidence=0.96, route="unsupported", entities={"unsupported_category": "missing_messaging_plugin"})
        if re.search(r"\b(book|reserve)\b.*\bflight\b", lowered):
            return IntentResult(intent="unsupported_travel_booking", capability="unsupported", confidence=0.95, route="unsupported", entities={"unsupported_category": "travel_booking"})

        if re.match(r"^\s*play\s+.+(?:\s+on\s+youtube|\s+song|\s+music)\s*$", lowered):
            return IntentResult(intent="play_media", capability="desktop.media_play_pause", confidence=0.92, route="desktop")

        if re.search(r"\b(make|create|generate|prepare)\b.*\b(notes?|ppt|presentation|assignment|questions?|quiz|rubric|outline|lesson plan|report|document|spreadsheet)\b", lowered):
            return IntentResult(intent="artifact_or_study_request", capability="ai.answer", confidence=0.8, route="backend_ai", entities={"artifact_request": True})

        if re.search(
            r"\b(explain|tell me|what is|what's|who is|why|how|write|draft|create|generate|"
            r"summarize|summarise|compare|plan|research|prepare|brief|teach|translate|define|"
            r"can you|could you|would you|give me|i want to know|what do you think|"
            r"do you think|your opinion|your thoughts|thoughts on|talk about|discuss|describe)\b|\?$",
            lowered,
        ):
            return IntentResult(intent="general_ai", capability="ai.answer", confidence=0.74, route="backend_ai")

        return IntentResult(intent="unsupported", capability="unsupported", confidence=0.5, route="unsupported")

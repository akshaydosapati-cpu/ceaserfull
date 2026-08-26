from __future__ import annotations

from core.schemas import CapabilityDefinition


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CapabilityDefinition] = {}

    def register(self, definition: CapabilityDefinition) -> None:
        self._items[definition.name] = definition

    def get(self, name: str | None) -> CapabilityDefinition | None:
        if not name:
            return None
        return self._items.get(name)

    def all(self) -> list[CapabilityDefinition]:
        return list(self._items.values())

    def categories(self) -> dict[str, list[CapabilityDefinition]]:
        grouped: dict[str, list[CapabilityDefinition]] = {}
        for item in self.all():
            grouped.setdefault(item.category, []).append(item)
        return grouped

    def discovery(self, runtime) -> list[dict]:
        discovered = []
        for item in self.all():
            if item.handler == "windows_runtime":
                available, reason = runtime.available(item.name)
            else:
                available, reason = True, ""
            if available:
                status = "available"
            elif "permission" in reason.lower():
                status = "permission_required"
            elif item.required_hardware:
                status = "limited"
            else:
                status = "unsupported"
            discovered.append({"capability_id": item.name, "category": item.category, "status": status, "reason": reason, "risk": item.risk_level})
        return discovered


def build_default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for name, description, risk, internet in [
        ("desktop.open_application", "Open a discovered Windows application.", "low", False),
        ("desktop.close_application", "Close a running Windows application.", "medium", False),
        ("desktop.close_browser_tab", "Close an explicitly identified or active browser tab.", "low", False),
        ("desktop.open_folder", "Open a local folder.", "low", False),
        ("desktop.open_file", "Open a local file.", "low", False),
        ("desktop.open_url", "Open a website URL.", "low", True),
        ("desktop.take_screenshot", "Capture a screenshot.", "low", False),
        ("desktop.set_volume", "Set or change system volume.", "low", False),
        ("desktop.get_battery", "Read local device battery status.", "low", False),
        ("desktop.media_play_pause", "Control media playback.", "low", False),
        ("desktop.lock_screen", "Lock the current Windows session.", "low", False),
        ("desktop.delete_file", "Delete a local file or folder after explicit confirmation.", "high", False),
        ("ai.answer", "Ask CEASER cloud AI for an answer.", "low", True),
        ("ai.weather", "Get current weather through the configured weather provider.", "low", True),
        ("ai.news", "Fetch current news headlines through the configured news provider.", "low", True),
        ("github.list_repositories", "List connected GitHub repositories.", "low", True),
        ("github.resolve_repository", "Resolve a connected GitHub repository.", "low", True),
        ("github.get_readme", "Read repository README content.", "low", True),
        ("github.list_commits", "List repository commits.", "low", True),
        ("github.list_issues", "List repository issues.", "low", True),
        ("github.list_pull_requests", "List repository pull requests.", "low", True),
        ("github.summarize_repository", "Summarize a connected GitHub repository.", "low", True),
        ("notion.search_pages", "Search connected Notion pages and databases.", "low", True),
        ("notion.get_page", "Read a connected Notion page.", "low", True),
        ("notion.list_tasks", "List connected Notion tasks.", "low", True),
        ("notion.create_page", "Create a Notion page after confirmation.", "medium", True),
        ("notion.append_blocks", "Append Notion blocks after confirmation.", "medium", True),
        ("cloud.list", "List CEASER cloud resources for the signed-in account.", "low", True),
        ("cloud.search", "Search CEASER cloud resources for the signed-in account.", "low", True),
        ("cloud.latest", "Find the latest CEASER cloud resource.", "low", True),
        ("cloud.read", "Read a CEASER cloud resource.", "low", True),
        ("cloud.create", "Create a CEASER cloud resource after confirmation.", "medium", True),
        ("cloud.update", "Update or rename a CEASER cloud resource after confirmation.", "medium", True),
        ("cloud.delete", "Delete a CEASER cloud resource after confirmation.", "high", True),
        ("cloud.restore", "Restore a deleted CEASER cloud resource.", "medium", True),
        ("cloud.upload", "Upload a file through CEASER cloud.", "medium", True),
        ("cloud.download", "Download a CEASER cloud resource.", "low", True),
        ("study.generate_viva_questions", "Generate viva questions from verified context.", "low", True),
        ("study.generate_revision_notes", "Generate revision notes from verified context.", "low", True),
        ("study.generate_quiz", "Generate a quiz from study notes.", "low", True),
        ("ai.summarize_activity", "Summarize GitHub activity into a work report.", "low", True),
        ("knowledge.query", "Query trusted CEASER product and system knowledge.", "low", False),
        ("knowledge.list_capabilities", "List CEASER capability knowledge.", "low", False),
        ("knowledge.get_workflow", "Get CEASER workflow knowledge.", "low", False),
        ("knowledge.get_safety_rule", "Get CEASER safety rule knowledge.", "low", False),
        ("knowledge.get_architecture_summary", "Get CEASER architecture knowledge.", "low", False),
        ("knowledge.refresh", "Refresh trusted CEASER knowledge sources.", "low", False),
        ("memory.remember", "Save a confirmed long-term user memory.", "low", False),
        ("memory.list", "List saved long-term memories for the signed-in user.", "low", False),
        ("memory.forget", "Delete selected long-term memories for the signed-in user.", "low", False),
        ("memory.disable_session", "Disable long-term memory capture for the current session.", "low", False),
        ("workflow.plan", "Route a multi-step workflow request to the future planner.", "medium", True),
        ("unsupported", "Unsupported command response.", "low", False),
    ]:
        if name.startswith("github.") or name.startswith("notion.") or name.startswith("cloud."):
            route = "integration"
        elif name.startswith("knowledge."):
            route = "knowledge"
        elif name.startswith("memory."):
            route = "memory"
        elif name.startswith("ai.") or name.startswith("study."):
            route = "backend_ai"
        elif name.startswith("workflow."):
            route = "workflow"
        else:
            route = "desktop"
        registry.register(
            CapabilityDefinition(
                name=name,
                description=description,
                handler="legacy_execute_single_step",
                route=route,
                risk_level=risk,  # type: ignore[arg-type]
                requires_internet=internet,
                requires_confirmation=name in {"notion.create_page", "notion.append_blocks", "desktop.delete_file", "cloud.create", "cloud.update", "cloud.delete", "cloud.restore", "cloud.upload"},
            )
        )
    windows = {
        "apps": ["app.list_installed", "app.search", "app.open", "app.close", "app.force_close", "app.focus", "app.list_running", "app.restart", "app.foreground", "app.windows"],
        "windows": ["window.list", "window.get_active", "window.focus", "window.minimize", "window.maximize", "window.restore", "window.close", "window.move", "window.resize", "window.snap_left", "window.snap_right", "window.fullscreen", "window.move_to_monitor", "window.show_desktop"],
        "system": ["system.open_settings", "system.open_task_manager", "system.open_file_explorer", "system.open_terminal", "system.open_calculator", "system.open_run", "system.lock", "system.sleep", "system.hibernate", "system.shutdown", "system.restart", "system.sign_out"],
        "network": ["network.status", "network.ip_info", "network.open_settings", "network.diagnostics", "wifi.status", "wifi.list_networks", "wifi.current_network", "wifi.connect", "wifi.disconnect", "wifi.enable", "wifi.disable", "bluetooth.status", "bluetooth.list_paired", "bluetooth.connect", "bluetooth.disconnect", "bluetooth.open_settings", "vpn.list", "vpn.connect", "vpn.disconnect", "hotspot.status", "hotspot.enable", "hotspot.disable", "airplane.status", "airplane.enable", "airplane.disable"],
        "audio": ["audio.volume.get", "audio.volume.set", "audio.volume.up", "audio.volume.down", "audio.mute", "audio.unmute", "audio.output.list", "audio.output.get", "audio.output.set", "audio.input.list", "audio.input.get", "audio.input.set", "audio.microphone_mute", "audio.microphone_unmute", "audio.app_volume.get", "audio.app_volume.set", "audio.app_mute", "audio.app_unmute"],
        "media": ["media.sessions.list", "media.current", "media.play", "media.pause", "media.play_pause", "media.stop", "media.next", "media.previous", "media.seek_forward", "media.seek_backward"],
        "display": ["display.list", "display.primary", "display.brightness.get", "display.brightness.set", "display.brightness.up", "display.brightness.down", "display.open_settings", "monitor.list", "monitor.primary"],
        "screenshots": ["screen.capture_all", "screen.capture_monitor", "screen.capture_active_window", "screen.capture_region"],
        "files": ["file.search", "file.list", "file.read", "file.create", "file.rename", "file.copy", "file.move", "file.delete", "file.restore", "file.stat", "file.open", "file.open_with", "file.reveal", "file.recent", "file.calculate_size", "directory.create", "directory.list", "directory.rename", "directory.copy", "directory.move", "directory.delete", "archive.compress", "archive.extract"],
        "clipboard": ["clipboard.read", "clipboard.write", "clipboard.clear", "clipboard.files"],
        "input": ["input.type_text", "input.hotkey", "input.copy", "input.cut", "input.paste", "input.select_all", "input.undo", "input.redo", "input.save"],
        "ui": ["ui.click", "ui.double_click", "ui.right_click", "ui.scroll", "ui.drag", "ui.focus_element"],
        "browser": ["browser.open", "browser.navigate", "browser.search", "browser.inspect", "browser.find", "browser.click", "browser.type", "browser.select", "browser.scroll", "browser.hover", "browser.wait", "browser.tab.list", "browser.tab.open", "browser.tab.close", "browser.tab.switch", "browser.back", "browser.forward", "browser.reload", "browser.upload", "browser.download", "browser.screenshot", "browser.extract", "browser.verify"],
        "power": ["power.battery_status", "power.battery_percentage", "power.charging_status", "power.battery_saver_status", "power.open_settings"],
        "storage": ["storage.drives", "storage.free_space", "storage.usage", "storage.large_files_search", "storage.open_drive", "storage.removable_devices", "storage.eject"],
        "peripherals": ["printer.list", "printer.default", "printer.status", "printer.print_file", "printer.queue", "printer.cancel_job", "printer.open_settings", "recycle.list", "recycle.restore", "recycle.empty"],
        "virtual_desktop": ["desktop_virtual.list", "desktop_virtual.switch", "desktop_virtual.create", "desktop_virtual.close"],
        "information": ["system.os_version", "system.device_name", "system.cpu_info", "system.memory_info", "system.disk_info", "system.battery_info", "system.network_info", "system.display_info"],
        "development": ["terminal.run_allowed", "process.list", "process.stop_authorized", "network.ping", "network.dns_lookup", "development.toolchain_status", "project.resolve", "project.create", "project.open", "project.files", "project.build", "project.test", "project.repair", "project.run", "project.stop", "project.open_vscode", "git.status", "git.diff", "git.add", "git.commit", "git.log"],
    }
    high = {"app.force_close", "file.delete", "directory.delete", "system.shutdown", "system.restart", "system.sign_out", "system.hibernate", "process.stop_authorized", "storage.eject", "recycle.empty", "printer.print_file"}
    medium = {"wifi.connect", "wifi.disconnect", "wifi.enable", "wifi.disable", "bluetooth.connect", "bluetooth.disconnect", "vpn.connect", "vpn.disconnect", "hotspot.enable", "hotspot.disable", "airplane.enable", "airplane.disable", "file.rename", "file.copy", "file.move", "directory.rename", "directory.copy", "directory.move", "input.type_text", "input.hotkey"}
    local_only = {"input.type_text", "input.hotkey", "input.cut", "input.paste", "process.stop_authorized", "terminal.run_allowed", "ui.click", "ui.double_click", "ui.right_click", "ui.scroll", "ui.drag", "ui.focus_element"}
    hardware = {"wifi": ["wifi_adapter"], "bluetooth": ["bluetooth_radio"], "display.brightness": ["brightness_control"], "monitor": ["multiple_displays"]}
    for category, names in windows.items():
        for name in names:
            risk = "high" if name in high else "medium" if name in medium else "low"
            required_hardware = next((items for prefix, items in hardware.items() if name.startswith(prefix)), [])
            registry.register(CapabilityDefinition(
                name=name, display_name=name.replace(".", " ").title(), category=category,
                description=f"Structured Windows capability: {name}.", handler="windows_runtime", route="desktop",
                risk_level=risk, requires_confirmation=name in high,
                confirmation_policy="always" if name in high else "remote" if name in medium else "none",
                local_execution_allowed=True, remote_execution_allowed=name not in local_only,
                required_os_features=["windows"], required_hardware=required_hardware,
                availability_probe=name, verification_handler=f"verify:{name}",
                cancellation_supported=name in {"file.search", "storage.large_files_search", "project.build", "project.test"},
                idempotent=name.endswith((".get", ".list", ".status")) or name.startswith(("network.", "power.")),
                activity_event_type="capability",
            ))
    return registry

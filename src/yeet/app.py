import asyncio
import json
import os
import shutil
import subprocess
import sys
from functools import cached_property
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, ClassVar

from textual import events, on, work
from textual.app import App
from textual.binding import Binding, BindingType
from textual.reactive import reactive, var

from yeet import atomic, paths
from yeet.settings import Schema, Settings
from yeet.settings_schema import SCHEMA

if TYPE_CHECKING:
    from yeet.screens.main import MainScreen
    from yeet.screens.settings import SettingsScreen


def get_settings_screen() -> SettingsScreen:
    from yeet.screens.settings import SettingsScreen

    return SettingsScreen()


class YeetApp(App, inherit_bindings=False):
    """Top-b git client app."""

    CSS_PATH = "yeet.tcss"
    SCREENS = {
        "settings": get_settings_screen,
    }
    BINDING_GROUP_TITLE = "System"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+c", "help_quit", show=False, system=True),
        Binding("f1", "toggle_help_panel", "Help", priority=True),
        Binding(
            "f2,ctrl+comma",
            "settings",
            "Settings",
            tooltip="Open settings",
        ),
    ]

    _settings = var(dict)
    auto_copy: reactive[bool] = reactive(True)
    last_ctrl_c_time = reactive(0.0)
    terminal_title: var[str] = var("Yeet")
    terminal_title_icon: var[str] = var("Git")
    project_dir = var(Path)

    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (100, "-wide")]
    PAUSE_GC_ON_SCROLL = True

    def __init__(self, project_dir: str | None = None) -> None:
        super().__init__()
        self.project_dir = Path(project_dir or "./").expanduser().resolve()
        self.start_time = monotonic()
        self._supports_pyperclip: bool | None = None

    @property
    def config_path(self) -> Path:
        return paths.get_config()

    @property
    def settings_path(self) -> Path:
        return paths.get_config() / "yeet.json"

    @cached_property
    def version(self) -> str:
        from yeet import get_version

        return get_version()

    @cached_property
    def term_program(self) -> str:
        if term_program := os.environ.get("TERM_PROGRAM"):
            return term_program
        if "WT_SESSION" in os.environ:
            return "Windows Terminal"
        if "KITTY_WINDOW_ID" in os.environ:
            return "Kitty"
        if "ALACRITTY_SOCKET" in os.environ or "ALACRITTY_LOG" in os.environ:
            return "Alacritty"
        if "VTE_VERSION" in os.environ:
            return "VTE-based"
        if "KONSOLE_VERSION" in os.environ:
            return "Konsole"
        return "Unknown"

    @cached_property
    def settings_schema(self) -> Schema:
        return Schema(SCHEMA)

    @cached_property
    def settings(self) -> Settings:
        return Settings(
            self.settings_schema,
            self._settings,
            on_set_callback=self.setting_updated,
        )

    async def on_load(self) -> None:
        settings_path = self.settings_path
        if settings_path.exists():
            settings = json.loads(settings_path.read_text("utf-8"))
        else:
            settings = {}
            settings_path.write_text(
                json.dumps(settings, indent=4, separators=(", ", ": ")),
                "utf-8",
            )
        if isinstance(settings.get("ui"), dict):
            ui_settings = settings["ui"]
            assert isinstance(ui_settings, dict)
            ui_settings.pop("column", None)
            ui_settings.pop("column-width", None)
        if isinstance(settings.get("sidebar"), dict):
            sidebar_settings = settings["sidebar"]
            assert isinstance(sidebar_settings, dict)
            sidebar_settings.pop("hide", None)
            if not sidebar_settings:
                settings.pop("sidebar", None)
        self._settings = settings
        self.settings.set_all()

    def on_mount(self) -> None:
        self.push_screen(self.get_main_screen())
        self.update_terminal_title()

    def get_main_screen(self) -> MainScreen:
        from yeet.screens.main import MainScreen

        project_path = Path(self.project_dir or "./").resolve().absolute()
        return MainScreen(project_path)

    def setting_updated(self, key: str, value: object) -> None:
        if key == "ui.theme" and isinstance(value, str):
            self.theme = value
        elif key == "ui.auto_copy" and isinstance(value, bool):
            self.auto_copy = value
        elif key == "ui.footer":
            self.set_class(not bool(value), "-hide-footer")

    def copy_to_clipboard(self, text: str) -> None:
        copied = False
        if self._supports_pyperclip is None:
            try:
                import pyperclip
            except ImportError:
                self._supports_pyperclip = False
            else:
                self._supports_pyperclip = True

        if self._supports_pyperclip:
            import pyperclip

            try:
                pyperclip.copy(text)
                copied = True
            except Exception:
                pass

        if not copied:
            try:
                if sys.platform == "darwin" and shutil.which("pbcopy"):
                    subprocess.run(["pbcopy"], input=text, text=True, check=True)
                    copied = True
                elif sys.platform.startswith("linux"):
                    if shutil.which("wl-copy"):
                        subprocess.run(["wl-copy"], input=text, text=True, check=True)
                        copied = True
                    elif shutil.which("xclip"):
                        subprocess.run(
                            ["xclip", "-selection", "clipboard"],
                            input=text,
                            text=True,
                            check=True,
                        )
                        copied = True
                    elif shutil.which("xsel"):
                        subprocess.run(
                            ["xsel", "--clipboard", "--input"],
                            input=text,
                            text=True,
                            check=True,
                        )
                        copied = True
            except Exception:
                pass
        super().copy_to_clipboard(text)

    @on(events.TextSelected)
    async def on_text_selected(self, _: events.TextSelected) -> None:
        if self.auto_copy:
            if (selection := self.screen.get_selected_text()) is not None:
                self.copy_to_clipboard(selection)
                self.notify("Copied selected text", title="Clipboard")

    async def save_settings(self, force: bool = False) -> None:
        await asyncio.to_thread(self._save_settings, force=force)

    def _save_settings(self, force: bool = False) -> None:
        if force or self.settings.changed:
            path = str(self.settings_path)
            try:
                atomic.write(path, self.settings.json)
            except Exception as error:
                self.notify(str(error), title="Settings", severity="error")
            else:
                self.settings.up_to_date()

    @work
    async def action_settings(self) -> None:
        await self.push_screen_wait("settings")
        await self.save_settings()

    async def action_quit(self) -> None:
        self.screen.set_focus(None)

        async def save_settings_and_exit() -> None:
            await self.save_settings()
            self.exit()

        self.set_timer(0.05, save_settings_and_exit)

    def action_help_quit(self) -> None:
        if monotonic() - self.last_ctrl_c_time <= 5.0:
            self.exit()
            return
        self.last_ctrl_c_time = monotonic()
        self.notify("Press [b]ctrl+c[/b] again to quit the app", title="Quit?")

    def action_toggle_help_panel(self) -> None:
        if self.screen.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()

    def update_terminal_title(self) -> None:
        screen_title = self.screen.title
        title = (
            f"{self.terminal_title} - {screen_title}"
            if screen_title
            else self.terminal_title
        )
        terminal_title = f"{self.terminal_title_icon} {title}"
        if driver := self._driver:
            driver.write(f"\033]0;{terminal_title}\007")

    def watch_terminal_title(self, _: str) -> None:
        self.update_terminal_title()

    def run_on_exit(self) -> None:
        return

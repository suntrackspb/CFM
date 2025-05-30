from __future__ import annotations
from typing import Any, Dict, Optional, Set, List
from textual.app import App
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from textual import events
from textual.containers import Horizontal, Vertical, Container
import os
import json
from file_panel import FilePanel
from dialogs import DialogConfirm, DialogInput
import shutil

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

class FileManagerApp(App):
    CSS_PATH = "theme.css"
    BINDINGS = [
        ("f5", "copy", "Copy"),
        ("f6", "move", "Move"),
        ("f7", "mkdir", "Create Folder"),
        ("f8", "delete", "Delete"),
        ("f9", "toggle_hidden", "Switch Hidden"),
        ("tab", "switch_panel", "Switch Panel"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        config: Dict[str, Any] = self.load_config()
        self.lang_code: str = config.get('lang', 'en')
        self.lang: Dict[str, str] = self.load_lang(self.lang_code)
        left_path: str = config.get('left_panel', os.path.expanduser('~'))
        right_path: str = config.get('right_panel', os.path.abspath(os.sep))
        show_hidden_left: bool = config.get('show_hidden_left', False)
        show_hidden_right: bool = config.get('show_hidden_right', False)
        self.left_panel: FilePanel = FilePanel(left_path, lang=self.lang, active=True, show_hidden=show_hidden_left)
        self.right_panel: FilePanel = FilePanel(right_path, lang=self.lang, active=False, show_hidden=show_hidden_right)
        self.active_panel: str = config.get('active_panel', 'left')

    def save_config(self) -> None:
        config: Dict[str, Any] = {
            'left_panel': self.left_panel.path,
            'right_panel': self.right_panel.path,
            'active_panel': self.active_panel,
            'lang': getattr(self, 'lang_code', 'en'),
            'show_hidden_left': self.left_panel.show_hidden,
            'show_hidden_right': self.right_panel.show_hidden,
        }
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f)
        except Exception:
            pass

    def load_config(self) -> Dict[str, Any]:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def set_active_panel(self, panel_name: str) -> None:
        self.active_panel = panel_name
        self.left_panel.active = (panel_name == 'left')
        self.right_panel.active = (panel_name == 'right')
        self.left_panel.refresh()
        self.right_panel.refresh()
        self.save_config()

    def load_lang(self, code: str) -> Dict[str, str]:
        path = os.path.join('lang', f'{code}.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def compose(self) -> Any:
        yield Header()
        yield Horizontal(
            Container(self.left_panel, id="left-panel", classes="panel-container"),
            Static("│", classes="divider"),
            Container(self.right_panel, id="right-panel", classes="panel-container"),
        )
        yield Footer()

    async def on_mount(self) -> None:
        self.set_active_panel(self.active_panel)

    async def on_key(self, event: events.Key) -> None:
        # Tab — переключение панели
        if event.key == "tab":
            await self.action_switch_panel()
            return
        # Делегируем ВСЕ стрелочные события (с модификаторами) и Enter/Backspace в активную панель
        if event.key in ("up", "down", "left", "right", "enter", "backspace"):
            if self.active_panel == 'left':
                await self.left_panel.on_key(event)
            else:
                await self.right_panel.on_key(event)

    async def action_switch_panel(self) -> None:
        if self.active_panel == 'left':
            self.set_active_panel('right')
        else:
            self.set_active_panel('left')

    async def action_copy(self) -> None:
        src_panel: FilePanel = self.left_panel if self.active_panel == 'left' else self.right_panel
        dst_panel: FilePanel = self.right_panel if self.active_panel == 'left' else self.left_panel
        indices: Set[int] = src_panel.selected_indices or {src_panel.selected}
        paths: List[str] = [os.path.join(src_panel.path, src_panel.files[i]['name']) for i in sorted(indices)]
        self._copy_queue: Optional[List[str]] = list(paths)
        self._copy_dst_panel: FilePanel = dst_panel
        self._copy_src_panel: FilePanel = src_panel
        self._copy_overwrite_all: bool = False
        await self._process_copy_queue()

    async def _process_copy_queue(self) -> None:
        while self._copy_queue:
            src_path = self._copy_queue.pop(0)
            dst_path = os.path.join(self._copy_dst_panel.path, os.path.basename(src_path))
            if os.path.exists(dst_path) and not self._copy_overwrite_all:
                dialog = DialogConfirm(
                    f"{self.lang['file_exists']} {os.path.basename(src_path)}\n{self.lang['overwrite']}?",
                    yes=self.lang["overwrite"],
                    no=self.lang["skip"],
                    cancel=self.lang["cancel"]
                )
                await self.mount(dialog)
                self.set_focus(dialog)
                self.dialog = dialog
                self.pending_copy_item = (src_path, dst_path)
                return
            self._do_copy(src_path, dst_path, self._copy_src_panel, self._copy_dst_panel)
        self._copy_src_panel.refresh_files()
        self._copy_dst_panel.refresh_files()
        self._copy_src_panel.refresh()
        self._copy_dst_panel.refresh()
        self._copy_queue = None
        self._copy_overwrite_all = False
        self.save_config()

    def _do_copy(self, src_path: str, dst_path: str, src_panel: FilePanel, dst_panel: FilePanel) -> None:
        try:
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst_path)
        except Exception:
            pass

    async def action_move(self) -> None:
        src_panel: FilePanel = self.left_panel if self.active_panel == 'left' else self.right_panel
        dst_panel: FilePanel = self.right_panel if self.active_panel == 'left' else self.left_panel
        indices: Set[int] = src_panel.selected_indices or {src_panel.selected}
        paths: List[str] = [os.path.join(src_panel.path, src_panel.files[i]['name']) for i in sorted(indices)]
        self._move_queue: Optional[List[str]] = list(paths)
        self._move_dst_panel: FilePanel = dst_panel
        self._move_src_panel: FilePanel = src_panel
        self._move_overwrite_all: bool = False
        await self._process_move_queue()

    async def _process_move_queue(self) -> None:
        while self._move_queue:
            src_path = self._move_queue.pop(0)
            dst_path = os.path.join(self._move_dst_panel.path, os.path.basename(src_path))
            if os.path.exists(dst_path) and not self._move_overwrite_all:
                dialog = DialogConfirm(
                    f"{self.lang['file_exists']} {os.path.basename(src_path)}\n{self.lang['overwrite']}?",
                    yes=self.lang["overwrite"],
                    no=self.lang["skip"],
                    cancel=self.lang["cancel"]
                )
                await self.mount(dialog)
                self.set_focus(dialog)
                self.dialog = dialog
                self.pending_move_item = (src_path, dst_path)
                return
            self._do_move(src_path, dst_path, self._move_src_panel, self._move_dst_panel)
        self._move_src_panel.refresh_files()
        self._move_dst_panel.refresh_files()
        self._move_src_panel.refresh()
        self._move_dst_panel.refresh()
        self._move_queue = None
        self._move_overwrite_all = False
        self.save_config()

    def _do_move(self, src_path: str, dst_path: str, src_panel: FilePanel, dst_panel: FilePanel) -> None:
        try:
            shutil.move(src_path, dst_path)
        except Exception:
            pass

    async def action_delete(self) -> None:
        panel: FilePanel = self.left_panel if self.active_panel == 'left' else self.right_panel
        indices: Set[int] = panel.selected_indices or {panel.selected}
        paths: List[str] = [os.path.join(panel.path, panel.files[i]['name']) for i in sorted(indices)]
        self._delete_queue: Optional[List[str]] = list(paths)
        self._delete_panel: FilePanel = panel
        await self._process_delete_queue()

    async def _process_delete_queue(self) -> None:
        while self._delete_queue:
            path = self._delete_queue.pop(0)
            name = os.path.basename(path)
            dialog = DialogConfirm(
                self.lang["confirm_delete"].format(name=name),
                yes=self.lang["yes"],
                no=self.lang["no"],
                cancel=self.lang["cancel"]
            )
            await self.mount(dialog)
            self.set_focus(dialog)
            self.dialog = dialog
            self.pending_delete_path = path
            self.pending_delete_panel = self._delete_panel
            return
        self._delete_panel.refresh_files()
        self._delete_panel.refresh()
        self._delete_queue = None
        self.save_config()

    async def on_dialog_confirm_result(self, message: Any) -> None:
        if not hasattr(self, 'dialog'):
            return
        # Массовое копирование
        if hasattr(self, 'pending_copy_item'):
            src_path, dst_path = self.pending_copy_item
            if message.result == "yes":
                self._do_copy(src_path, dst_path, self._copy_src_panel, self._copy_dst_panel)
            elif message.result == "cancel":
                self._copy_queue = []
            del self.pending_copy_item
            await self.dialog.remove()
            if hasattr(self, 'dialog'):
                del self.dialog
            await self._process_copy_queue()
            return
        # Массовое перемещение
        if hasattr(self, 'pending_move_item'):
            src_path, dst_path = self.pending_move_item
            if message.result == "yes":
                self._do_move(src_path, dst_path, self._move_src_panel, self._move_dst_panel)
            elif message.result == "cancel":
                self._move_queue = []
            del self.pending_move_item
            await self.dialog.remove()
            if hasattr(self, 'dialog'):
                del self.dialog
            await self._process_move_queue()
            return
        # Массовое удаление
        if hasattr(self, 'pending_delete_path'):
            path = self.pending_delete_path
            panel = self.pending_delete_panel
            if message.result == "yes":
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except Exception:
                    pass
            del self.pending_delete_path
            del self.pending_delete_panel
            await self.dialog.remove()
            if hasattr(self, 'dialog'):
                del self.dialog
            await self._process_delete_queue()
            return
        # Старые одиночные операции (на всякий случай)
        if hasattr(self, 'pending_copy'):
            src_path, dst_path, src_panel, dst_panel = self.pending_copy
            if message.result == "yes":
                self._do_copy(src_path, dst_path, src_panel, dst_panel)
            del self.pending_copy
        elif hasattr(self, 'pending_move'):
            src_path, dst_path, src_panel, dst_panel = self.pending_move
            if message.result == "yes":
                self._do_move(src_path, dst_path, src_panel, dst_panel)
            del self.pending_move
        elif hasattr(self, 'pending_delete_path'):
            if message.result == "yes":
                try:
                    if os.path.isdir(self.pending_delete_path):
                        shutil.rmtree(self.pending_delete_path)
                    else:
                        os.remove(self.pending_delete_path)
                except Exception:
                    pass
                self.pending_delete_panel.refresh_files()
                self.pending_delete_panel.refresh()
            del self.pending_delete_path
            del self.pending_delete_panel
        await self.dialog.remove()
        if hasattr(self, 'dialog'):
            del self.dialog

    async def action_mkdir(self) -> None:
        panel: FilePanel = self.left_panel if self.active_panel == 'left' else self.right_panel
        dialog = DialogInput(
            self.lang["enter_folder_name"],
            ok=self.lang["create"],
            cancel=self.lang["cancel"]
        )
        await self.mount(dialog)
        self.set_focus(dialog)
        self.dialog = dialog
        self.pending_panel = panel

    async def on_dialog_input_result(self, message: Any) -> None:
        if not hasattr(self, 'dialog'):
            return
        if message.confirmed and message.value.strip():
            folder_name: str = message.value.strip()
            panel: FilePanel = self.pending_panel
            new_path: str = os.path.join(panel.path, folder_name)
            try:
                os.mkdir(new_path)
            except Exception:
                pass
            panel.refresh_files()
            panel.refresh()
        await self.dialog.remove()
        del self.dialog
        if hasattr(self, 'pending_panel'):
            del self.pending_panel

    async def action_open_or_enter(self) -> None:
        panel: FilePanel = self.left_panel if self.active_panel == 'left' else self.right_panel
        selected_path: Optional[str] = panel.get_selected_path()
        if selected_path and os.path.isdir(selected_path):
            panel.enter_selected()
            panel.refresh()
        elif selected_path and os.path.isfile(selected_path):
            panel.open_selected_file()

    async def action_up(self) -> None:
        if self.active_panel == 'left':
            await self.left_panel.on_key(events.Key("left", ""))
        else:
            await self.right_panel.on_key(events.Key("left", ""))

    async def action_toggle_hidden(self) -> None:
        if self.active_panel == 'left':
            self.left_panel.show_hidden = not self.left_panel.show_hidden
            self.left_panel.refresh_files()
            self.left_panel.refresh()
        else:
            self.right_panel.show_hidden = not self.right_panel.show_hidden
            self.right_panel.refresh_files()
            self.right_panel.refresh()
        self.save_config()

if __name__ == "__main__":
    FileManagerApp().run() 
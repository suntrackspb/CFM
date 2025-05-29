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

class FileManagerApp(App):
    CSS_PATH = "theme.css"
    BINDINGS = [
        ("f5", "copy", "Copy"),
        ("f6", "move", "Move"),
        ("f7", "mkdir", "Create Folder"),
        ("f8", "delete", "Delete"),
        ("tab", "switch_panel", "Switch Panel"),
        ("right", "open_or_enter", "Open/Enter"),
        ("enter", "open_or_enter", "Open/Enter"),
        ("left", "up", "Up"),
        ("backspace", "up", "Up"),
        ("cmd+shift+.", "toggle_hidden", "Show/Hide Hidden (Mac)"),
        ("win+shift+.", "toggle_hidden", "Show/Hide Hidden (Win/Linux)"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lang = self.load_lang('en')
        home = os.path.expanduser('~')
        root = os.path.abspath(os.sep)
        self.left_panel = FilePanel(home, lang=self.lang, active=True)
        self.right_panel = FilePanel(root, lang=self.lang, active=False)
        self.active_panel = 'left'

    def load_lang(self, code):
        path = os.path.join('lang', f'{code}.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def compose(self):
        yield Header()
        yield Horizontal(
            Container(self.left_panel, id="left-panel", classes="panel-container"),
            Static("│", classes="divider"),
            Container(self.right_panel, id="right-panel", classes="panel-container"),
        )
        yield Footer()

    async def on_mount(self) -> None:
        # TODO: инициализация панелей, загрузка сессии, языков
        pass

    async def on_key(self, event: events.Key) -> None:
        # Обработка Tab для переключения панели
        if event.key == "tab":
            await self.action_switch_panel()
            return
        # Пробрасываем только стрелки вверх/вниз для перемещения по списку
        if event.key in ("up", "down"):
            if self.active_panel == 'left':
                await self.left_panel.on_key(event)
            else:
                await self.right_panel.on_key(event)

    async def action_switch_panel(self):
        # Переключение активной панели
        if self.active_panel == 'left':
            self.left_panel.active = False
            self.right_panel.active = True
            self.active_panel = 'right'
        else:
            self.left_panel.active = True
            self.right_panel.active = False
            self.active_panel = 'left'
        self.left_panel.refresh()
        self.right_panel.refresh()

    async def action_copy(self):
        src_panel = self.left_panel if self.active_panel == 'left' else self.right_panel
        dst_panel = self.right_panel if self.active_panel == 'left' else self.left_panel
        # Массовое копирование
        indices = src_panel.selected_indices or {src_panel.selected}
        paths = [os.path.join(src_panel.path, src_panel.files[i]['name']) for i in sorted(indices)]
        self._copy_queue = list(paths)
        self._copy_dst_panel = dst_panel
        self._copy_src_panel = src_panel
        self._copy_overwrite_all = False
        await self._process_copy_queue()

    async def _process_copy_queue(self):
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

    def _do_copy(self, src_path, dst_path, src_panel, dst_panel):
        try:
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst_path)
        except Exception:
            pass

    async def action_move(self):
        src_panel = self.left_panel if self.active_panel == 'left' else self.right_panel
        dst_panel = self.right_panel if self.active_panel == 'left' else self.left_panel
        indices = src_panel.selected_indices or {src_panel.selected}
        paths = [os.path.join(src_panel.path, src_panel.files[i]['name']) for i in sorted(indices)]
        self._move_queue = list(paths)
        self._move_dst_panel = dst_panel
        self._move_src_panel = src_panel
        self._move_overwrite_all = False
        await self._process_move_queue()

    async def _process_move_queue(self):
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

    def _do_move(self, src_path, dst_path, src_panel, dst_panel):
        try:
            shutil.move(src_path, dst_path)
        except Exception:
            pass

    async def action_delete(self):
        panel = self.left_panel if self.active_panel == 'left' else self.right_panel
        indices = panel.selected_indices or {panel.selected}
        paths = [os.path.join(panel.path, panel.files[i]['name']) for i in sorted(indices)]
        self._delete_queue = list(paths)
        self._delete_panel = panel
        await self._process_delete_queue()

    async def _process_delete_queue(self):
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

    async def on_dialog_confirm_result(self, message):
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

    async def action_mkdir(self):
        panel = self.left_panel if self.active_panel == 'left' else self.right_panel
        dialog = DialogInput(
            self.lang["enter_folder_name"],
            ok=self.lang["create"],
            cancel=self.lang["cancel"]
        )
        await self.mount(dialog)
        self.set_focus(dialog)
        self.dialog = dialog
        self.pending_panel = panel

    async def on_dialog_input_result(self, message):
        if not hasattr(self, 'dialog'):
            return
        if message.confirmed and message.value.strip():
            folder_name = message.value.strip()
            panel = self.pending_panel
            new_path = os.path.join(panel.path, folder_name)
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

    async def action_open_or_enter(self):
        panel = self.left_panel if self.active_panel == 'left' else self.right_panel
        selected_path = panel.get_selected_path()
        if selected_path and os.path.isdir(selected_path):
            panel.enter_selected()
            panel.refresh()
        elif selected_path and os.path.isfile(selected_path):
            panel.open_selected_file()

    async def action_up(self):
        # Вверх по папке
        if self.active_panel == 'left':
            await self.left_panel.on_key(events.Key("left", ""))
        else:
            await self.right_panel.on_key(events.Key("left", ""))

    async def action_toggle_hidden(self):
        # Переключение отображения скрытых файлов
        if self.active_panel == 'left':
            self.left_panel.show_hidden = not self.left_panel.show_hidden
            self.left_panel.refresh_files()
            self.left_panel.refresh()
        else:
            self.right_panel.show_hidden = not self.right_panel.show_hidden
            self.right_panel.refresh_files()
            self.right_panel.refresh()

if __name__ == "__main__":
    FileManagerApp().run() 
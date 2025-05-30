from __future__ import annotations
from typing import Any, Dict, Optional, Set
from textual.widget import Widget
from textual.reactive import reactive
from textual import events
import os
import datetime

class FilePanel(Widget):
    def __init__(self, path: str, show_hidden: bool = False, lang: Optional[Dict[str, str]] = None, active: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path: str = path
        self.show_hidden: bool = show_hidden
        self.lang: Dict[str, str] = lang or {}
        self.files: list[Dict[str, Any]] = []
        self.selected: int = 0
        self.active: bool = active
        self.selected_indices: Set[int] = set()  # Для множественного выделения
        self.last_selected: Optional[int] = None  # Для Shift-выделения
        self.drag_select_start: Optional[int] = None  # Для протяжки мышью
        self.drag_select_button: Optional[int] = None
        self._scroll_offset: int = 0  # Для вертикального скроллинга
        self.refresh_files()

    def refresh_files(self) -> None:
        try:
            entries = os.listdir(self.path)
            if not self.show_hidden:
                entries = [e for e in entries if not e.startswith('.')]
            files = []
            for entry in entries:
                full_path = os.path.join(self.path, entry)
                stat = os.stat(full_path)
                is_dir = os.path.isdir(full_path)
                name, ext = os.path.splitext(entry)
                files.append({
                    'name': entry,
                    'ext': ext[1:] if ext else '',
                    'size': stat.st_size if not is_dir else '',
                    'date': datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'is_dir': is_dir,
                    'hidden': entry.startswith('.')
                })
            files.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            self.files = files
            self.selected_indices = {i for i in self.selected_indices if i < len(self.files)}
            if self.selected >= len(self.files):
                self.selected = max(0, len(self.files) - 1)
            self._ensure_selected_visible()
        except Exception as e:
            self.files = []

    def _ensure_selected_visible(self) -> None:
        max_rows = self.size.height - 3  # 1 — заголовок, 2 — рамка Panel
        if max_rows < 1:
            max_rows = 1
        if self.selected < self._scroll_offset:
            self._scroll_offset = self.selected
        elif self.selected >= self._scroll_offset + max_rows:
            self._scroll_offset = self.selected - max_rows + 1
        if self._scroll_offset < 0:
            self._scroll_offset = 0

    def enter_selected(self) -> None:
        if not self.files:
            return
        selected_file = self.files[self.selected]
        if selected_file['is_dir']:
            self.path = os.path.join(self.path, selected_file['name'])
            self.selected = 0
            self.selected_indices = set()
            self.last_selected = None
            self._scroll_offset = 0
            self.refresh_files()
            if hasattr(self, 'app'):
                self.app.save_config()

    def go_up(self) -> None:
        parent = os.path.dirname(self.path)
        if parent and parent != self.path:
            self.path = parent
            self.selected = 0
            self.selected_indices = set()
            self.last_selected = None
            self._scroll_offset = 0
            self.refresh_files()
            if hasattr(self, 'app'):
                self.app.save_config()

    def get_selected_path(self) -> Optional[str]:
        if not self.files:
            return None
        return os.path.join(self.path, self.files[self.selected]['name'])

    def open_selected_file(self) -> None:
        selected = self.get_selected_path()
        if not selected or os.path.isdir(selected):
            return
        import subprocess
        import sys
        try:
            if sys.platform.startswith('darwin'):
                subprocess.Popen(['open', selected])
            elif sys.platform.startswith('win'):
                os.startfile(selected)
            else:
                subprocess.Popen(['xdg-open', selected])
        except Exception as e:
            pass

    def render(self) -> Any:
        from rich.table import Table
        from rich.text import Text
        from rich.panel import Panel
        table = Table(show_header=True, header_style="bold", box=None, expand=True)
        table.add_column(self.lang.get('name', 'Name'), width=30, overflow="ellipsis")
        table.add_column(self.lang.get('ext', 'Ext'), width=6)
        table.add_column(self.lang.get('size', 'Size'), justify="right", width=10)
        table.add_column(self.lang.get('date', 'Date'), width=17)
        max_rows = self.size.height - 3  # 1 — заголовок, 2 — рамка Panel
        if max_rows < 1:
            max_rows = 1
        visible_files = self.files[self._scroll_offset:self._scroll_offset + max_rows]
        for idx, f in enumerate(visible_files, start=self._scroll_offset):
            if idx in self.selected_indices:
                style = "on #66d9ef bold black"  # Выделенные файлы
            elif idx == self.selected and self.active:
                style = "on #49483e"
            elif f['hidden']:
                style = "dim"
            else:
                style = ""
            table.add_row(
                Text(f['name'], style=style),
                Text(f['ext'], style=style),
                Text(str(f['size']), style=style),
                Text(f['date'], style=style)
            )
        title = f"{self.path}"
        border_style = "bold #66d9ef" if self.active else "#49483e"
        return Panel(table, title=title, border_style=border_style, expand=True)

    async def on_key(self, event: events.Key) -> None:
        if not self.active:
            return
        key = event.key.lower()
        # Пробел — добавить/убрать текущий файл в выделение
        if key == "space":
            if self.selected in self.selected_indices:
                self.selected_indices.remove(self.selected)
            else:
                self.selected_indices.add(self.selected)
            self.last_selected = self.selected
            self.refresh()
            return
        # 'm' — диапазонное выделение от last_selected до текущего
        if key == "m":
            if self.last_selected is not None and self.last_selected != self.selected:
                start = min(self.last_selected, self.selected)
                end = max(self.last_selected, self.selected)
                for i in range(start, end + 1):
                    self.selected_indices.add(i)
            else:
                self.selected_indices.add(self.selected)
            self.last_selected = self.selected
            self.refresh()
            return
        if key == "up":
            self.selected = max(0, self.selected - 1)
            self.last_selected = self.selected
            self.selected_indices = {self.selected}
            self._ensure_selected_visible()
            self.refresh()
        elif key == "down":
            self.selected = min(len(self.files) - 1, self.selected + 1)
            self.last_selected = self.selected
            self.selected_indices = {self.selected}
            self._ensure_selected_visible()
            self.refresh()
        elif key in ("right", "enter"):
            if self.files:
                if self.files[self.selected]['is_dir']:
                    self.enter_selected()
                    self._ensure_selected_visible()
                    self.refresh()
                else:
                    self.open_selected_file()
        elif key in ("left", "backspace"):
            self.go_up()
            self._ensure_selected_visible()
            self.refresh()

    async def on_mouse_down(self, event: Any) -> None:
        if not hasattr(event, 'y'):
            return
        row = event.y - self.region.y - 1  # 0 — заголовок
        max_rows = self.size.height - 3
        if max_rows < 1:
            max_rows = 1
        row = min(max(row, 0), max_rows - 1)
        file_idx = self._scroll_offset + row
        if file_idx < 0 or file_idx >= len(self.files):
            return
        ctrl = getattr(event, 'ctrl', False)
        shift = getattr(event, 'shift', False)
        right = getattr(event, 'button', 1) == 3  # ПКМ
        self.selected = file_idx
        if right:
            if self.drag_select_start is None:
                if file_idx in self.selected_indices:
                    self.selected_indices.remove(file_idx)
                else:
                    self.selected_indices.add(file_idx)
                self.last_selected = file_idx
                self.drag_select_start = file_idx
                self.drag_select_button = 3
        elif ctrl:
            if file_idx in self.selected_indices:
                self.selected_indices.remove(file_idx)
            else:
                self.selected_indices.add(file_idx)
            self.last_selected = file_idx
        elif shift and self.last_selected is not None:
            start = min(self.last_selected, file_idx)
            end = max(self.last_selected, file_idx)
            for i in range(start, end + 1):
                self.selected_indices.add(i)
        else:
            self.selected_indices = {file_idx}
            self.last_selected = file_idx
        self._ensure_selected_visible()
        self.refresh()
        self.app.set_focus(self)
        self.app.active_panel = 'left' if self is self.app.left_panel else 'right'
        self.app.left_panel.active = self is self.app.left_panel
        self.app.right_panel.active = self is self.app.right_panel
        self.app.left_panel.refresh()
        self.app.right_panel.refresh()

    async def on_mouse_move(self, event: Any) -> None:
        if self.drag_select_start is not None and self.drag_select_button == 3:
            row = event.y - self.region.y - 1
            max_rows = self.size.height - 3
            if max_rows < 1:
                max_rows = 1
            row = min(max(row, 0), max_rows - 1)
            file_idx = self._scroll_offset + row
            if file_idx < 0:
                file_idx = 0
            if file_idx >= len(self.files):
                file_idx = len(self.files) - 1
            start = min(self.drag_select_start, file_idx)
            end = max(self.drag_select_start, file_idx)
            self.selected_indices = set(range(start, end + 1))
            self.selected = file_idx
            self._ensure_selected_visible()
            self.refresh()

    async def on_mouse_up(self, event: Any) -> None:
        if getattr(event, 'button', 1) == 3:
            self.drag_select_start = None
            self.drag_select_button = None

    async def on_double_click(self, event: Any) -> None:
        if not hasattr(event, 'y'):
            return
        row = event.y - self.region.y - 1
        max_rows = self.size.height - 3
        if max_rows < 1:
            max_rows = 1
        row = min(max(row, 0), max_rows - 1)
        file_idx = self._scroll_offset + row
        if file_idx < 0 or file_idx >= len(self.files):
            return
        self.selected = file_idx
        self.selected_indices = {file_idx}
        self.last_selected = file_idx
        f = self.files[file_idx]
        path = os.path.join(self.path, f['name'])
        if f['is_dir']:
            self.path = path
            self.selected = 0
            self.selected_indices = set()
            self.last_selected = None
            self._scroll_offset = 0
            self.refresh_files()
            self.refresh()
        else:
            self.open_selected_file() 
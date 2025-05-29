from textual.widget import Widget
from textual.reactive import reactive
from textual import events
import os
import datetime

class FilePanel(Widget):
    def __init__(self, path, show_hidden=False, lang=None, active=False, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.show_hidden = show_hidden
        self.lang = lang or {}
        self.files = []
        self.selected = 0
        self.active = active
        self.selected_indices = set()  # Для множественного выделения
        self.last_selected = None  # Для Shift-выделения
        self.drag_select_start = None  # Для протяжки мышью
        self.drag_select_button = None
        self.refresh_files()

    def refresh_files(self):
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
            # Сброс выделения если файлов стало меньше
            self.selected_indices = {i for i in self.selected_indices if i < len(self.files)}
            if self.selected >= len(self.files):
                self.selected = max(0, len(self.files) - 1)
        except Exception as e:
            self.files = []

    def enter_selected(self):
        if not self.files:
            return
        selected_file = self.files[self.selected]
        if selected_file['is_dir']:
            self.path = os.path.join(self.path, selected_file['name'])
            self.selected = 0
            self.selected_indices = set()
            self.last_selected = None
            self.refresh_files()

    def go_up(self):
        parent = os.path.dirname(self.path)
        if parent and parent != self.path:
            self.path = parent
            self.selected = 0
            self.selected_indices = set()
            self.last_selected = None
            self.refresh_files()

    def get_selected_path(self):
        if not self.files:
            return None
        return os.path.join(self.path, self.files[self.selected]['name'])

    def open_selected_file(self):
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

    def render(self):
        from rich.table import Table
        from rich.text import Text
        from rich.panel import Panel
        table = Table(show_header=True, header_style="bold", box=None, expand=True)
        table.add_column(self.lang.get('name', 'Name'))
        table.add_column(self.lang.get('ext', 'Ext'), width=6)
        table.add_column(self.lang.get('size', 'Size'), justify="right", width=10)
        table.add_column(self.lang.get('date', 'Date'), width=17)
        for idx, f in enumerate(self.files):
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

    async def on_key(self, event: events.Key):
        if not self.active:
            return
        if event.key == "up":
            self.selected = max(0, self.selected - 1)
            self.refresh()
        elif event.key == "down":
            self.selected = min(len(self.files) - 1, self.selected + 1)
            self.refresh()
        elif event.key in ("right", "enter"):
            if self.files and self.files[self.selected]['is_dir']:
                self.enter_selected()
                self.refresh()
        elif event.key in ("left", "backspace"):
            self.go_up()
            self.refresh()
        # Навигация и другие действия будут добавлены позже 

    async def on_mouse_down(self, event):
        if not hasattr(event, 'y'):
            return
        row = event.y - self.region.y - 1  # 0 — заголовок
        if row < 0 or row >= len(self.files):
            return
        ctrl = getattr(event, 'ctrl', False)
        shift = getattr(event, 'shift', False)
        right = getattr(event, 'button', 1) == 3  # ПКМ
        self.selected = row
        if right:
            if self.drag_select_start is None:
                # Одиночный ПКМ — добавить/убрать из выделения
                if row in self.selected_indices:
                    self.selected_indices.remove(row)
                else:
                    self.selected_indices.add(row)
                self.last_selected = row
                # Готовимся к протяжке
                self.drag_select_start = row
                self.drag_select_button = 3
        elif ctrl:
            if row in self.selected_indices:
                self.selected_indices.remove(row)
            else:
                self.selected_indices.add(row)
            self.last_selected = row
        elif shift and self.last_selected is not None:
            start = min(self.last_selected, row)
            end = max(self.last_selected, row)
            for i in range(start, end + 1):
                self.selected_indices.add(i)
        else:
            self.selected_indices = {row}
            self.last_selected = row
        self.refresh()
        self.app.set_focus(self)
        self.app.active_panel = 'left' if self is self.app.left_panel else 'right'
        self.app.left_panel.active = self is self.app.left_panel
        self.app.right_panel.active = self is self.app.right_panel
        self.app.left_panel.refresh()
        self.app.right_panel.refresh()

    async def on_mouse_move(self, event):
        if self.drag_select_start is not None and self.drag_select_button == 3:
            row = event.y - self.region.y - 1
            if row < 0:
                row = 0
            if row >= len(self.files):
                row = len(self.files) - 1
            start = min(self.drag_select_start, row)
            end = max(self.drag_select_start, row)
            self.selected_indices = set(range(start, end + 1))
            self.selected = row
            self.refresh()

    async def on_mouse_up(self, event):
        if getattr(event, 'button', 1) == 3:
            self.drag_select_start = None
            self.drag_select_button = None

    async def on_double_click(self, event):
        if not hasattr(event, 'y'):
            return
        row = event.y - self.region.y - 1
        if row < 0 or row >= len(self.files):
            return
        self.selected = row
        self.selected_indices = {row}
        self.last_selected = row
        f = self.files[row]
        path = os.path.join(self.path, f['name'])
        if f['is_dir']:
            self.path = path
            self.selected = 0
            self.selected_indices = set()
            self.last_selected = None
            self.refresh_files()
            self.refresh()
        else:
            self.open_selected_file() 
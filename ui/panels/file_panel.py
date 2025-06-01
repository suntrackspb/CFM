"""
Панель файлов для двухпанельного файлового менеджера.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Optional, Set, TYPE_CHECKING

from textual.widget import Widget
from textual.widgets import DataTable, Static
from textual.containers import Vertical
from textual import events
from textual.message import Message

from models.config import PanelConfig
from models.file_item import FileItem
from utils.helpers import get_file_type, get_file_style, open_file_external

if TYPE_CHECKING:
    from core.language_manager import LanguageManager

logger = logging.getLogger(__name__)


class DirectoryChanged(Message):
    """Сообщение об изменении директории."""
    
    def __init__(self, panel_id: str, new_path: Path) -> None:
        super().__init__()
        self.panel_id = panel_id
        self.new_path = new_path


class SelectionChanged(Message):
    """Сообщение об изменении выделения."""
    
    def __init__(self, panel_id: str, selected_count: int) -> None:
        super().__init__()
        self.panel_id = panel_id
        self.selected_count = selected_count


class FilePanel(Widget):
    """
    Панель файлов с навигацией и операциями над файлами.
    """
    
    def __init__(
        self,
        config: PanelConfig,
        language_manager: LanguageManager,
        panel_id: str,
        is_active: bool = False,
        **kwargs
    ):
        """
        Инициализирует панель файлов.
        
        Args:
            config: Конфигурация панели
            language_manager: Менеджер языков
            panel_id: Идентификатор панели (left/right)
            is_active: Активна ли панель
        """
        super().__init__(**kwargs)
        self.config = config
        self.language_manager = language_manager
        self.panel_id = panel_id
        self.is_active_panel = is_active
        
        # Состояние панели
        self.current_path = config.path
        self.show_hidden = config.show_hidden
        self.selected_index = config.selected_index
        self.file_items: List[FileItem] = []
        self.selected_items: Set[int] = set()  # Индексы выделенных элементов
        
        # UI компоненты
        self.path_bar: Optional[Static] = None
        self.file_table: Optional[DataTable] = None

    def compose(self):
        """Создает структуру панели."""
        with Vertical(classes=f"file-panel {'active' if self.is_active_panel else 'inactive'}"):
            # Строка пути
            self.path_bar = Static(
                str(self.current_path),
                classes="path-bar"
            )
            yield self.path_bar
            
            # Таблица файлов
            self.file_table = DataTable(
                cursor_type="row",
                zebra_stripes=True,
                classes="file-table"
            )
            yield self.file_table

    async def on_mount(self) -> None:
        """Инициализация после монтирования."""
        if self.file_table:
            # Настраиваем колонки таблицы
            self.file_table.add_column(
                self.language_manager.get_text("name", "Name"),
                width=40
            )
            self.file_table.add_column(
                self.language_manager.get_text("size", "Size"),
                width=10
            )
            self.file_table.add_column(
                self.language_manager.get_text("date", "Date"),
                width=16
            )
            
        await self.load_directory()

    async def load_directory(self, path: Optional[Path] = None) -> None:
        """
        Загружает содержимое директории.
        
        Args:
            path: Путь к директории. Если None, использует current_path.
        """
        if path is not None:
            self.current_path = path
            self.config.path = path
            
        try:
            # Проверяем существование и права доступа
            if not self.current_path.exists():
                self.current_path = Path.home()
                self.config.path = self.current_path
                
            if not self.current_path.is_dir():
                self.current_path = self.current_path.parent
                self.config.path = self.current_path
                
            # Получаем список файлов
            self.file_items = []
            items = []
            
            # Добавляем родительскую директорию если не в корне
            if self.current_path != self.current_path.parent:
                parent_item = FileItem.create_parent_item(self.current_path)
                items.append(parent_item)
                
            # Читаем содержимое директории
            try:
                for item_path in self.current_path.iterdir():
                    try:
                        file_item = FileItem.from_path(item_path)
                        
                        # Фильтруем скрытые файлы
                        if file_item.is_hidden and not self.show_hidden:
                            continue
                            
                        items.append(file_item)
                    except OSError as e:
                        logger.warning(f"Не удается получить информацию о {item_path}: {e}")
                        continue
                        
            except PermissionError:
                logger.error(f"Нет доступа к директории: {self.current_path}")
                # Можно показать ошибку пользователю
                
            # Сортируем: сначала папки, потом файлы, по имени
            items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
            self.file_items = items
            
            # Обновляем UI
            await self._update_table()
            self._update_path_bar()
            
            # Восстанавливаем выделение
            if 0 <= self.selected_index < len(self.file_items):
                if self.file_table:
                    try:
                        self.file_table.move_cursor(row=self.selected_index)
                    except Exception:
                        pass
            else:
                self.selected_index = 0
                if self.file_table and self.file_items:
                    try:
                        self.file_table.move_cursor(row=0)
                    except Exception:
                        pass
                    
            # Очищаем множественное выделение
            self.selected_items.clear()
            
            self.post_message(DirectoryChanged(self.panel_id, self.current_path))
            logger.info(f"Загружена директория: {self.current_path}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки директории {self.current_path}: {e}")

    async def _update_table(self) -> None:
        """Обновляет содержимое таблицы."""
        if not self.file_table:
            return
            
        # Очищаем таблицу
        self.file_table.clear()
        
        # Добавляем строки
        for i, item in enumerate(self.file_items):
            # Определяем стиль элемента
            file_type = get_file_type(f".{item.extension}")
            is_selected = i in self.selected_items
            is_active = (i == self.selected_index and self.is_active_panel)
            
            style = get_file_style(
                file_type,
                item.is_hidden,
                is_selected,
                is_active
            )
            
            # Форматируем имя
            name = item.name
            if item.is_dir:
                name = f"[{name}]" if name != ".." else name
                
            # Добавляем строку
            self.file_table.add_row(
                name,
                item.format_size(),
                item.format_date(),
                key=str(i)
            )

    def _update_path_bar(self) -> None:
        """Обновляет строку пути."""
        if self.path_bar:
            self.path_bar.update(str(self.current_path))

    async def handle_key(self, event: events.Key) -> None:
        """Обрабатывает нажатия клавиш."""
        if not self.is_active_panel:
            return
            
        key = event.key
        
        if key == "up":
            await self._move_cursor(-1)
        elif key == "down":
            await self._move_cursor(1)
        elif key == "enter":
            await self._activate_current_item()
        elif key == "backspace":
            await self._go_parent()
        elif key == "space":
            await self._toggle_selection()
        elif key == "ctrl+a":
            await self._select_all()
        elif key.startswith("ctrl+") and key[5:].isdigit():
            # Быстрый переход по цифрам
            index = int(key[5:]) - 1
            if 0 <= index < len(self.file_items):
                await self._move_cursor_to(index)

    async def _move_cursor(self, delta: int) -> None:
        """Перемещает курсор на delta позиций."""
        if not self.file_items:
            return
            
        new_index = max(0, min(len(self.file_items) - 1, self.selected_index + delta))
        if new_index != self.selected_index:
            self.selected_index = new_index
            self.config.selected_index = new_index
            
            if self.file_table:
                # Используем метод move_cursor вместо прямого присвоения
                try:
                    self.file_table.move_cursor(row=new_index)
                except Exception:
                    # Если move_cursor не работает, пытаемся другие методы
                    pass
                
            await self._update_table()  # Обновляем для изменения стилей

    async def _move_cursor_to(self, index: int) -> None:
        """Перемещает курсор к указанному индексу."""
        if 0 <= index < len(self.file_items):
            self.selected_index = index
            self.config.selected_index = index
            
            if self.file_table:
                try:
                    self.file_table.move_cursor(row=index)
                except Exception:
                    pass
                
            await self._update_table()

    async def _activate_current_item(self) -> None:
        """Активирует текущий элемент (открывает файл или входит в папку)."""
        if not self.file_items or self.selected_index >= len(self.file_items):
            return
            
        item = self.file_items[self.selected_index]
        
        if item.is_dir:
            await self.load_directory(item.path)
        else:
            # Открываем файл во внешнем приложении
            if not open_file_external(item.path):
                logger.warning(f"Не удалось открыть файл: {item.path}")

    async def _go_parent(self) -> None:
        """Переходит в родительскую директорию."""
        parent_path = self.current_path.parent
        if parent_path != self.current_path:
            await self.load_directory(parent_path)

    async def _toggle_selection(self) -> None:
        """Переключает выделение текущего элемента."""
        if not self.file_items or self.selected_index >= len(self.file_items):
            return
            
        # Не позволяем выделять ".."
        if self.file_items[self.selected_index].name == "..":
            return
            
        if self.selected_index in self.selected_items:
            self.selected_items.remove(self.selected_index)
        else:
            self.selected_items.add(self.selected_index)
            
        await self._update_table()
        self.post_message(SelectionChanged(self.panel_id, len(self.selected_items)))

    async def _select_all(self) -> None:
        """Выделяет все элементы кроме '..'."""
        self.selected_items.clear()
        
        for i, item in enumerate(self.file_items):
            if item.name != "..":
                self.selected_items.add(i)
                
        await self._update_table()
        self.post_message(SelectionChanged(self.panel_id, len(self.selected_items)))

    def get_selected_items(self) -> List[FileItem]:
        """Возвращает список выделенных элементов."""
        if not self.selected_items:
            # Если ничего не выделено, возвращаем текущий элемент
            if (self.file_items and 
                0 <= self.selected_index < len(self.file_items) and
                self.file_items[self.selected_index].name != ".."):
                return [self.file_items[self.selected_index]]
            return []
            
        selected = []
        for index in self.selected_items:
            if index < len(self.file_items):
                selected.append(self.file_items[index])
        return selected

    def set_active(self, active: bool) -> None:
        """Устанавливает активность панели."""
        self.is_active_panel = active
        
        # Обновляем CSS класс
        if active:
            self.add_class("active")
            self.remove_class("inactive")
        else:
            self.add_class("inactive")
            self.remove_class("active")

    async def toggle_hidden_files(self) -> None:
        """Переключает отображение скрытых файлов."""
        self.show_hidden = not self.show_hidden
        self.config.show_hidden = self.show_hidden
        await self.load_directory()

    async def reload_content(self) -> None:
        """Обновляет содержимое панели."""
        await self.load_directory()

    def clear_selection(self) -> None:
        """Очищает множественное выделение."""
        self.selected_items.clear()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Обрабатывает выбор строки в таблице."""
        if event.data_table == self.file_table:
            self.selected_index = event.cursor_row
            self.config.selected_index = self.selected_index

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Обрабатывает подсветку строки в таблице."""
        if event.data_table == self.file_table:
            self.selected_index = event.cursor_row
            self.config.selected_index = self.selected_index 
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
        self.calculated_sizes: dict[Path, int] = {}  # Кэш размеров папок
        self.is_calculating = False  # Флаг процесса подсчета
        self._scroll_offset: int = 0  # Для собственного скроллинга
        
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
                cursor_type="none",  # Отключаем встроенный курсор
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
                # Позиция корректна, оставляем как есть
                pass
            else:
                # Сбрасываем на начало
                self.selected_index = 0
            
            # Сбрасываем скролл при смене директории
            self._scroll_offset = 0
            
            # Обеспечиваем видимость выбранного элемента
            self._ensure_selected_visible()
            
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
        
        # Вычисляем видимые элементы
        # Используем значение по умолчанию если размер еще не определен
        if self.file_table.size.height > 3:
            max_rows = max(1, self.file_table.size.height - 3)
        else:
            max_rows = 20  # Значение по умолчанию для первого рендера
            
        visible_start = self._scroll_offset
        visible_end = min(len(self.file_items), self._scroll_offset + max_rows)
        visible_items = self.file_items[visible_start:visible_end]
        
        # Добавляем строки для видимых элементов
        for i, item in enumerate(visible_items, start=visible_start):
            is_selected = i in self.selected_items
            is_current = (i == self.selected_index)
            
            # Используем безопасные символы (не конфликтующие с Rich markup)
            if item.is_dir:
                if item.name == "..":
                    display_name = "⟨..⟩"
                else:
                    display_name = f"⟨{item.name}⟩"
            else:
                display_name = item.name
            
            # Добавляем индикатор состояния
            if is_current:
                display_name = f"▶ {display_name}"
            elif is_selected:
                display_name = f"● {display_name}"
            else:
                display_name = f"  {display_name}"
            
            # Возвращаем красивые цвета
            if is_current and self.is_active_panel:
                if item.is_dir:
                    display_name = f"[white on blue]{display_name}[/white on blue]"
                else:
                    display_name = f"[black on yellow]{display_name}[/black on yellow]"
            elif is_current:
                display_name = f"[dim]{display_name}[/dim]"
            elif is_selected:
                display_name = f"[blue]{display_name}[/blue]"
            elif item.is_dir:
                display_name = f"[cyan]{display_name}[/cyan]"
            elif item.is_hidden:
                display_name = f"[dim]{display_name}[/dim]"
                
            # Добавляем строку
            self.file_table.add_row(
                display_name,
                self._get_display_size(item),
                item.format_date(),
                key=str(i)
            )

    def _get_display_size(self, item: FileItem) -> str:
        """Возвращает размер для отображения (обычный или вычисленный)."""
        if item.is_dir and item.path in self.calculated_sizes:
            # Показываем вычисленный размер папки
            calculated_size = self.calculated_sizes[item.path]
            return self._format_calculated_size(calculated_size)
        else:
            # Показываем обычный размер (пустой для папок, реальный для файлов)
            return item.format_size()

    def _update_path_bar(self) -> None:
        """Обновляет строку пути."""
        if self.path_bar:
            self.path_bar.update(str(self.current_path))

    def _ensure_selected_visible(self) -> None:
        """Обеспечивает видимость выбранного элемента через скроллинг."""
        if not self.file_table:
            return
            
        # Вычисляем количество видимых строк с защитой от неинициализированного размера
        if self.file_table.size.height > 3:
            max_rows = max(1, self.file_table.size.height - 3)  # -3 для заголовка и границ
        else:
            max_rows = 20  # Значение по умолчанию
        
        # Корректируем скролл чтобы выбранный элемент был виден
        if self.selected_index < self._scroll_offset:
            self._scroll_offset = self.selected_index
        elif self.selected_index >= self._scroll_offset + max_rows:
            self._scroll_offset = self.selected_index - max_rows + 1
            
        # Убеждаемся что скролл не уходит в отрицательные значения
        if self._scroll_offset < 0:
            self._scroll_offset = 0

    async def handle_key(self, event: events.Key) -> None:
        """Обрабатывает нажатия клавиш."""
        if not self.is_active_panel:
            return
            
        key = event.key
        logger.debug(f"Панель {self.panel_id} обрабатывает клавишу: {key}")
        
        if key == "up":
            await self._move_cursor(-1)
            event.prevent_default()
            event.stop()
        elif key == "down":
            await self._move_cursor(1)
            event.prevent_default()
            event.stop()
        elif key == "left":
            # Стрелка влево - выход на уровень выше
            await self._go_parent()
            event.prevent_default()
            event.stop()
        elif key == "right":
            # Стрелка вправо - вход в папку или запуск файла
            await self._activate_current_item()
            event.prevent_default()
            event.stop()
        elif key == "enter":
            await self._activate_current_item()
            event.prevent_default()
            event.stop()
        elif key == "backspace":
            await self._go_parent()
            event.prevent_default()
            event.stop()
        elif key == "space":
            await self._toggle_selection()
            event.prevent_default()
            event.stop()
        elif key == "pageup":
            # Page Up - прыжок на 10 элементов вверх
            await self._move_cursor(-10)
            event.prevent_default()
            event.stop()
        elif key == "pagedown":
            # Page Down - прыжок на 10 элементов вниз
            await self._move_cursor(10)
            event.prevent_default()
            event.stop()
        elif key == "home":
            # Home - в начало списка
            await self._move_cursor_to(0)
            event.prevent_default()
            event.stop()
        elif key == "end":
            # End - в конец списка
            if self.file_items:
                await self._move_cursor_to(len(self.file_items) - 1)
            event.prevent_default()
            event.stop()
        elif key == "ctrl+a":
            await self._select_all()
            event.prevent_default()
            event.stop()
        elif key.startswith("ctrl+") and key[5:].isdigit():
            # Быстрый переход по цифрам
            index = int(key[5:]) - 1
            if 0 <= index < len(self.file_items):
                await self._move_cursor_to(index)
            event.prevent_default()
            event.stop()

    async def _move_cursor(self, delta: int) -> None:
        """Перемещает курсор на delta позиций."""
        if not self.file_items:
            return
            
        old_index = self.selected_index
        new_index = max(0, min(len(self.file_items) - 1, self.selected_index + delta))
        if new_index != self.selected_index:
            self.selected_index = new_index
            self.config.selected_index = new_index
            logger.debug(f"Курсор перемещен с {old_index} на {new_index}")
            
            # Обеспечиваем видимость выбранного элемента
            self._ensure_selected_visible()
            
            # Обновляем отображение
            await self._update_table()

    async def _move_cursor_to(self, index: int) -> None:
        """Перемещает курсор к указанному индексу."""
        if 0 <= index < len(self.file_items):
            self.selected_index = index
            self.config.selected_index = index
            
            # Обеспечиваем видимость выбранного элемента
            self._ensure_selected_visible()
            
            # Обновляем отображение
            await self._update_table()

    async def _activate_current_item(self) -> None:
        """Активирует текущий элемент (открывает файл или входит в папку)."""
        if not self.file_items or self.selected_index >= len(self.file_items):
            logger.warning(f"Неверный индекс: {self.selected_index}, всего элементов: {len(self.file_items)}")
            return
            
        item = self.file_items[self.selected_index]
        logger.info(f"Активация элемента {self.selected_index}: {item.name} ({'папка' if item.is_dir else 'файл'})")
        
        if item.is_dir:
            await self.load_directory(item.path)
        else:
            # Открываем файл во внешнем приложении
            if not open_file_external(item.path):
                logger.warning(f"Не удалось открыть файл: {item.path}")

    async def _go_parent(self) -> None:
        """Переходит в родительскую директорию."""
        parent_path = self.current_path.parent
        # Проверяем, что мы не в корне системы
        if parent_path != self.current_path:
            await self.load_directory(parent_path)
        else:
            logger.debug(f"Уже в корневой директории: {self.current_path}")

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
        old_active = self.is_active_panel
        self.is_active_panel = active
        
        # Обновляем CSS класс
        if active:
            self.add_class("active")
            self.remove_class("inactive")
        else:
            self.add_class("inactive")
            self.remove_class("active")
            
        # Обновляем отображение если активность изменилась
        if old_active != active:
            # Запускаем обновление таблицы асинхронно
            from asyncio import create_task
            try:
                create_task(self._update_table())
            except Exception:
                pass  # Игнорируем ошибки при обновлении

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

    async def calculate_directory_sizes(self) -> None:
        """Подсчитывает размеры всех папок в текущей директории."""
        if self.is_calculating:
            return
            
        self.is_calculating = True
        self.calculated_sizes.clear()
        
        try:
            # Обновляем путь чтобы показать что идет подсчет
            if self.path_bar:
                original_text = str(self.current_path)
                self.path_bar.update(f"{original_text} (Calculating sizes...)")
            
            # Подсчитываем размеры только для папок
            for item in self.file_items:
                if item.is_dir and item.name != "..":
                    try:
                        size = await self._calculate_directory_size(item.path)
                        self.calculated_sizes[item.path] = size
                        
                        # Обновляем отображение по мере подсчета
                        await self._update_table()
                        
                    except Exception as e:
                        logger.warning(f"Не удалось подсчитать размер {item.path}: {e}")
                        continue
            
            # Восстанавливаем путь
            if self.path_bar:
                self.path_bar.update(original_text)
                
        finally:
            self.is_calculating = False
            await self._update_table()

    async def _calculate_directory_size(self, path: Path) -> int:
        """
        Рекурсивно подсчитывает размер директории.
        
        Args:
            path: Путь к директории
            
        Returns:
            int: Размер в байтах
        """
        total_size = 0
        
        try:
            for item in path.rglob('*'):
                try:
                    if item.is_file():
                        total_size += item.stat().st_size
                except (OSError, PermissionError):
                    # Пропускаем файлы к которым нет доступа
                    continue
        except (OSError, PermissionError):
            # Нет доступа к директории
            pass
            
        return total_size

    def _format_calculated_size(self, size: int) -> str:
        """
        Форматирует вычисленный размер директории.
        
        Args:
            size: Размер в байтах
            
        Returns:
            str: Отформатированный размер
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    # Убираем обработчики DataTable - они конфликтуют с нашей логикой навигации 
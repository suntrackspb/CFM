"""
Основной пользовательский интерфейс файлового менеджера.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal, Vertical
from textual import events
from textual.message import Message

from models.config import AppConfig
from models.file_item import FileItem
from ui.panels.file_panel import FilePanel
from ui.dialogs.base import ConfirmDialog, InputDialog, DialogResult
from utils.helpers import validate_filename

if TYPE_CHECKING:
    from core.language_manager import LanguageManager
    from core.file_operations import FileOperationsManager

logger = logging.getLogger(__name__)


class PanelSwitched(Message):
    """Сообщение о переключении панели."""
    
    def __init__(self, active_panel: str) -> None:
        super().__init__()
        self.active_panel = active_panel


class FileManagerUI(Widget):
    """
    Основной интерфейс файлового менеджера с двумя панелями.
    """
    
    def __init__(
        self,
        config: AppConfig,
        language_manager: LanguageManager,
        file_operations: FileOperationsManager,
        **kwargs
    ):
        """
        Инициализирует UI файлового менеджера.
        
        Args:
            config: Конфигурация приложения
            language_manager: Менеджер языков
            file_operations: Менеджер файловых операций
        """
        super().__init__(**kwargs)
        self.config = config
        self.language_manager = language_manager
        self.file_operations = file_operations
        
        # Панели файлов
        self.left_panel: Optional[FilePanel] = None
        self.right_panel: Optional[FilePanel] = None
        self.active_panel_side = config.active_panel
        
        # Статус бар
        self.status_bar: Optional[Static] = None

    def compose(self):
        """Создает структуру UI."""
        with Vertical():
            with Horizontal(classes="panels-container"):
                # Левая панель
                self.left_panel = FilePanel(
                    config=self.config.left_panel,
                    language_manager=self.language_manager,
                    panel_id="left",
                    is_active=(self.active_panel_side == "left"),
                    classes="file-panel"
                )
                yield self.left_panel
                
                # Разделитель
                yield Static("│", classes="panel-separator")
                
                # Правая панель
                self.right_panel = FilePanel(
                    config=self.config.right_panel,
                    language_manager=self.language_manager,
                    panel_id="right",
                    is_active=(self.active_panel_side == "right"),
                    classes="file-panel"
                )
                yield self.right_panel
                
            # Статус бар
            self.status_bar = Static(
                self._get_status_text(),
                classes="status-bar"
            )
            yield self.status_bar

    async def initialize(self) -> None:
        """Инициализирует панели после создания."""
        if self.left_panel:
            await self.left_panel.load_directory()
        if self.right_panel:
            await self.right_panel.load_directory()
        self._update_status()

    async def switch_active_panel(self) -> None:
        """Переключает активную панель."""
        if self.active_panel_side == "left":
            self.active_panel_side = "right"
            if self.left_panel:
                self.left_panel.set_active(False)
            if self.right_panel:
                self.right_panel.set_active(True)
                self.right_panel.focus()
        else:
            self.active_panel_side = "left"
            if self.right_panel:
                self.right_panel.set_active(False)
            if self.left_panel:
                self.left_panel.set_active(True)
                self.left_panel.focus()
                
        self.config.active_panel = self.active_panel_side
        self._update_status()
        self.post_message(PanelSwitched(self.active_panel_side))

    def get_active_panel(self) -> Optional[FilePanel]:
        """Возвращает активную панель."""
        if self.active_panel_side == "left":
            return self.left_panel
        else:
            return self.right_panel

    def get_inactive_panel(self) -> Optional[FilePanel]:
        """Возвращает неактивную панель."""
        if self.active_panel_side == "left":
            return self.right_panel
        else:
            return self.left_panel

    async def copy_selected(self) -> None:
        """Копирует выбранные файлы в неактивную панель."""
        active_panel = self.get_active_panel()
        inactive_panel = self.get_inactive_panel()
        
        if not active_panel or not inactive_panel:
            return
            
        selected_items = active_panel.get_selected_items()
        if not selected_items:
            return
            
        destination_dir = inactive_panel.current_path
        
        # Показываем диалог подтверждения
        message = self.language_manager.get_text(
            "copy_confirm",
            "Copy {count} items to {destination}?",
            count=len(selected_items),
            destination=str(destination_dir)
        )
        
        confirmed = await self._show_confirm_dialog(
            message,
            self.language_manager.get_text("copy", "Copy")
        )
        
        if confirmed:
            try:
                results = await self.file_operations.copy_items(
                    selected_items, destination_dir
                )
                await inactive_panel.reload_content()
                self._show_operation_results(results, "copy")
            except Exception as e:
                logger.error(f"Ошибка копирования: {e}")
                await self._show_error_dialog(str(e))

    async def move_selected(self) -> None:
        """Перемещает выбранные файлы в неактивную панель."""
        active_panel = self.get_active_panel()
        inactive_panel = self.get_inactive_panel()
        
        if not active_panel or not inactive_panel:
            return
            
        selected_items = active_panel.get_selected_items()
        if not selected_items:
            return
            
        destination_dir = inactive_panel.current_path
        
        # Показываем диалог подтверждения
        message = self.language_manager.get_text(
            "move_confirm",
            "Move {count} items to {destination}?",
            count=len(selected_items),
            destination=str(destination_dir)
        )
        
        confirmed = await self._show_confirm_dialog(
            message,
            self.language_manager.get_text("move", "Move")
        )
        
        if confirmed:
            try:
                results = await self.file_operations.move_items(
                    selected_items, destination_dir
                )
                await active_panel.reload_content()
                await inactive_panel.reload_content()
                self._show_operation_results(results, "move")
            except Exception as e:
                logger.error(f"Ошибка перемещения: {e}")
                await self._show_error_dialog(str(e))

    async def delete_selected(self) -> None:
        """Удаляет выбранные файлы."""
        active_panel = self.get_active_panel()
        
        if not active_panel:
            return
            
        selected_items = active_panel.get_selected_items()
        if not selected_items:
            return
            
        # Показываем диалог подтверждения
        message = self.language_manager.get_text(
            "delete_confirm",
            "Delete {count} items permanently?",
            count=len(selected_items)
        )
        
        confirmed = await self._show_confirm_dialog(
            message,
            self.language_manager.get_text("delete", "Delete")
        )
        
        if confirmed:
            try:
                results = await self.file_operations.delete_items(selected_items)
                await active_panel.reload_content()
                self._show_operation_results(results, "delete")
            except Exception as e:
                logger.error(f"Ошибка удаления: {e}")
                await self._show_error_dialog(str(e))

    async def create_directory(self) -> None:
        """Создает новую директорию."""
        active_panel = self.get_active_panel()
        if not active_panel:
            return
            
        # Показываем диалог ввода имени
        dialog = InputDialog(
            prompt=self.language_manager.get_text("enter_folder_name", "Enter folder name:"),
            title=self.language_manager.get_text("create_folder", "Create Folder"),
            validator=validate_filename,
            language_manager=self.language_manager
        )
        
        await self.app.push_screen(dialog)

    async def toggle_hidden_files(self) -> None:
        """Переключает отображение скрытых файлов."""
        active_panel = self.get_active_panel()
        if active_panel:
            await active_panel.toggle_hidden_files()
            self._update_status()

    async def refresh_panels(self) -> None:
        """Обновляет содержимое обеих панелей."""
        if self.left_panel:
            await self.left_panel.reload_content()
        if self.right_panel:
            await self.right_panel.reload_content()

    async def show_help(self) -> None:
        """Показывает окно помощи."""
        help_text = self.language_manager.get_text(
            "help_content",
            """Горячие клавиши:
Tab - переключить панель
F3 - подсчитать размеры папок
F5 - копировать, F6 - переместить
F7 - создать папку, F8 - удалить
F9 - скрытые файлы, F10 - обновить
Навигация:
↑↓ - перемещение курсора
←  - выход на уровень выше
→  - вход в папку / запуск файла
PageUp/PageDown - быстрый переход (10 элементов)
Home/End - в начало/конец списка
Enter - то же что →
Backspace - то же что ←
Пробел - выделить/снять
Ctrl+A - выделить все"""
        )
        
        dialog = ConfirmDialog(
            message=help_text,
            title=self.language_manager.get_text("help", "Help"),
            show_cancel=False,
            no_text=self.language_manager.get_text("close", "Close"),
            language_manager=self.language_manager,
            dialog_type="help"
        )
        
        # Используем push_screen для модального диалога
        await self.app.push_screen(dialog)

    async def calculate_sizes(self) -> None:
        """Подсчитывает размеры папок в активной панели."""
        active_panel = self.get_active_panel()
        if active_panel:
            await active_panel.calculate_directory_sizes()
            self._update_status()

    async def handle_key(self, event: events.Key) -> None:
        """Обрабатывает клавиши для UI."""
        # Делегируем обработку активной панели
        active_panel = self.get_active_panel()
        if active_panel:
            await active_panel.handle_key(event)

    async def handle_dialog_result(self, message: DialogResult) -> None:
        """Обрабатывает результаты диалогов."""
        # Обрабатываем только диалоги создания директории
        if (message.dialog_type == "input" and 
            isinstance(message.result, str) and 
            message.confirmed):
            # Обработка создания директории
            active_panel = self.get_active_panel()
            if active_panel and validate_filename(message.result):
                try:
                    result = await self.file_operations.create_directory(
                        active_panel.current_path, message.result
                    )
                    if result.result.value == "success":
                        await active_panel.reload_content()
                    else:
                        await self._show_error_dialog(
                            result.error_message or "Unknown error"
                        )
                except Exception as e:
                    logger.error(f"Ошибка создания директории: {e}")
                    await self._show_error_dialog(str(e))

    def save_state_to_config(self) -> None:
        """Сохраняет состояние UI в конфигурацию."""
        if self.left_panel:
            self.config.left_panel.path = self.left_panel.current_path
            self.config.left_panel.selected_index = self.left_panel.selected_index
            self.config.left_panel.show_hidden = self.left_panel.show_hidden
            
        if self.right_panel:
            self.config.right_panel.path = self.right_panel.current_path
            self.config.right_panel.selected_index = self.right_panel.selected_index
            self.config.right_panel.show_hidden = self.right_panel.show_hidden
            
        self.config.active_panel = self.active_panel_side

    async def _show_confirm_dialog(self, message: str, title: str) -> bool:
        """Показывает диалог подтверждения."""
        dialog = ConfirmDialog(
            message=message,
            title=title,
            language_manager=self.language_manager
        )
        
        await self.app.push_screen(dialog)
        
        # В реальной реализации здесь должно быть асинхронное ожидание результата
        # Пока возвращаем True для тестирования
        return True

    async def _show_error_dialog(self, error: str) -> None:
        """Показывает диалог ошибки."""
        dialog = ConfirmDialog(
            message=error,
            title=self.language_manager.get_text("error", "Error"),
            show_cancel=False,
            no_text=self.language_manager.get_text("close", "Close"),
            language_manager=self.language_manager
        )
        
        await self.app.push_screen(dialog)

    def _show_operation_results(self, results: List, operation: str) -> None:
        """Показывает результаты операции."""
        success_count = sum(1 for r in results if r.result.value == "success")
        total_count = len(results)
        
        message = self.language_manager.get_text(
            f"{operation}_complete",
            f"{operation.capitalize()} complete: {success_count}/{total_count}",
            success=success_count,
            total=total_count
        )
        
        self._update_status(message)

    def _get_status_text(self) -> str:
        """Возвращает текст для статус бара."""
        active_panel = self.get_active_panel()
        if active_panel:
            selected_count = len(active_panel.get_selected_items())
            total_count = len(active_panel.file_items)
            
            if selected_count > 0:
                return self.language_manager.get_text(
                    "status_selected",
                    "Selected: {selected} of {total}",
                    selected=selected_count,
                    total=total_count
                )
            else:
                return self.language_manager.get_text(
                    "status_total",
                    "Total: {total} items",
                    total=total_count
                )
        return ""

    def _update_status(self, message: Optional[str] = None) -> None:
        """Обновляет статус бар."""
        if self.status_bar:
            if message:
                self.status_bar.update(message)
            else:
                self.status_bar.update(self._get_status_text()) 
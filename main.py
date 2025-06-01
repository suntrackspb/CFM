"""
Основное приложение файлового менеджера.
Рефакторированная версия с улучшенной архитектурой.
"""
from __future__ import annotations
import logging
import asyncio
from pathlib import Path
from typing import Optional

from textual.app import App
from textual.widgets import Header, Footer
from textual.containers import Horizontal, Container
from textual import events

from core.config_manager import ConfigManager
from core.language_manager import LanguageManager
from core.file_operations import FileOperationsManager, ConflictResolver, OperationType
from ui.app_ui import FileManagerUI
from ui.dialogs.base import ConfirmDialog, InputDialog, DialogResult, ConflictDialog
from utils.constants import KEY_BINDINGS, THEME_FILENAME
from utils.helpers import resource_path, validate_filename


# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log', mode='w', encoding='utf-8'),  # Все в файл
        # logging.StreamHandler()  # Убираем вывод в консоль
    ]
)
logger = logging.getLogger(__name__)

# Включаем DEBUG для конкретных модулей
logging.getLogger('ui.dialogs.base').setLevel(logging.DEBUG)
logging.getLogger('ui.app_ui').setLevel(logging.DEBUG)


class UIConflictResolver(ConflictResolver):
    """Resolver конфликтов для UI."""
    
    def __init__(self, app: 'FileManagerApp'):
        self.app = app
        
    async def resolve_conflict(self, source: Path, destination: Path, operation_type: OperationType) -> str:
        """Показывает диалог разрешения конфликта."""
        message = self.app.language_manager.get_text(
            "file_exists_confirm", 
            "File already exists: {filename}\nOverwrite?",
            filename=destination.name
        )
        
        dialog = ConflictDialog(
            message=message,
            title=self.app.language_manager.get_text("conflict", "File Conflict"),
            yes_text=self.app.language_manager.get_text("overwrite", "Overwrite"),
            no_text=self.app.language_manager.get_text("skip", "Skip"),
            cancel_text=self.app.language_manager.get_text("cancel", "Cancel"),
            language_manager=self.app.language_manager,
            dialog_type="conflict"
        )
        
        # Показываем диалог и ждем результат
        result = await self.app.push_screen(dialog)
        
        # Возвращаем соответствующий результат
        if result == "yes":
            return "overwrite"
        elif result == "no":
            return "skip"
        else:
            return "cancel"


class FileManagerApp(App):
    """
    Главное приложение файлового менеджера.
    Координирует взаимодействие между компонентами.
    """
    
    CSS_PATH = resource_path(THEME_FILENAME)
    
    BINDINGS = [
        (KEY_BINDINGS['help'], "help", "Help"),
        (KEY_BINDINGS['calculate_sizes'], "calculate_sizes", "Calculate Sizes"),
        (KEY_BINDINGS['copy'], "copy", "Copy"),
        (KEY_BINDINGS['move'], "move", "Move"),
        (KEY_BINDINGS['mkdir'], "mkdir", "Create Folder"),
        (KEY_BINDINGS['delete'], "delete", "Delete"),
        (KEY_BINDINGS['toggle_hidden'], "toggle_hidden", "Toggle Hidden"),
        (KEY_BINDINGS['switch_panel'], "switch_panel", "Switch Panel"),
        (KEY_BINDINGS['refresh'], "refresh", "Refresh"),
        (KEY_BINDINGS['quit'], "quit", "Quit")
    ]

    def __init__(self, **kwargs):
        """Инициализирует приложение."""
        super().__init__(**kwargs)
        
        # Инициализируем менеджеры
        self.config_manager = ConfigManager()
        self.language_manager = LanguageManager()
        
        # Загружаем конфигурацию и языки
        self.config = self.config_manager.load_config()
        self.language_manager.load_all_languages()
        self.language_manager.set_language(self.config.language)
        
        # Инициализируем менеджер файловых операций
        conflict_resolver = UIConflictResolver(self)
        self.file_operations = FileOperationsManager(conflict_resolver)
        
        # Создаем UI
        self.ui: Optional[FileManagerUI] = None
        
        logger.info("Файловый менеджер инициализирован")

    def compose(self):
        """Создает структуру приложения."""
        yield Header()
        
        # Создаем основной UI
        self.ui = FileManagerUI(
            config=self.config,
            language_manager=self.language_manager,
            file_operations=self.file_operations
        )
        yield self.ui
        
        yield Footer()

    async def on_mount(self) -> None:
        """Обработчик события монтирования приложения."""
        if self.ui:
            await self.ui.initialize()
        logger.info("Приложение запущено")

    async def on_unmount(self) -> None:
        """Обработчик события размонтирования приложения."""
        # Сохраняем конфигурацию при выходе
        if self.ui:
            self.ui.save_state_to_config()
        self.config_manager.save_config()
        logger.info("Приложение завершено")

    # Обработчики действий
    async def action_help(self) -> None:
        """Показывает окно помощи."""
        if self.ui:
            await self.ui.show_help()

    async def action_calculate_sizes(self) -> None:
        """Подсчитывает размеры папок."""
        if self.ui:
            await self.ui.calculate_sizes()

    async def action_copy(self) -> None:
        """Копирует выбранные файлы."""
        if self.ui:
            await self.ui.copy_selected()

    async def action_move(self) -> None:
        """Перемещает выбранные файлы."""
        if self.ui:
            await self.ui.move_selected()

    async def action_delete(self) -> None:
        """Удаляет выбранные файлы."""
        if self.ui:
            await self.ui.delete_selected()

    async def action_mkdir(self) -> None:
        """Создает новую папку."""
        if self.ui:
            await self.ui.create_directory()

    async def action_toggle_hidden(self) -> None:
        """Переключает отображение скрытых файлов."""
        if self.ui:
            await self.ui.toggle_hidden_files()

    async def action_switch_panel(self) -> None:
        """Переключает активную панель."""
        if self.ui:
            await self.ui.switch_active_panel()

    async def action_refresh(self) -> None:
        """Обновляет содержимое панелей."""
        if self.ui:
            await self.ui.refresh_panels()

    async def action_quit(self) -> None:
        """Выходит из приложения."""
        self.exit()

    async def on_key(self, event: events.Key) -> None:
        """Обработчик клавиш."""
        # Сначала проверяем глобальные горячие клавиши
        key = event.key
        
        # Глобальные горячие клавиши (только функциональные)
        if key == KEY_BINDINGS['switch_panel']:  # Tab
            await self.action_switch_panel()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['help']:  # F1
            await self.action_help()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['calculate_sizes']:  # F3
            await self.action_calculate_sizes()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['copy']:  # F5
            await self.action_copy()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['move']:  # F6
            await self.action_move()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['mkdir']:  # F7
            await self.action_mkdir()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['delete']:  # F8
            await self.action_delete()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['toggle_hidden']:  # F9
            await self.action_toggle_hidden()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['refresh']:  # F10
            await self.action_refresh()
            event.prevent_default()
            event.stop()
            return
        elif key == KEY_BINDINGS['quit']:  # Ctrl+Q
            await self.action_quit()
            event.prevent_default()
            event.stop()
            return
        
        # Все остальные клавиши (навигационные) делегируем в UI
        if self.ui:
            await self.ui.handle_key(event)

    def get_language_text(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """Получает локализованный текст."""
        return self.language_manager.get_text(key, default, **kwargs)

    def save_config(self) -> None:
        """Сохраняет конфигурацию."""
        if self.ui:
            self.ui.save_state_to_config()
        self.config_manager.save_config()


def main():
    """Точка входа в приложение."""
    try:
        app = FileManagerApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main() 
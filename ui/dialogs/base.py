"""
Базовые классы для диалоговых окон.
"""
from __future__ import annotations
from abc import abstractmethod
from typing import Any, Optional, Dict, Callable
from textual.screen import Screen
from textual.widgets import Button, Static
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual import events
from core.language_manager import LanguageManager
import logging

logger = logging.getLogger(__name__)


class DialogResult(Message):
    """Базовое сообщение результата диалога."""
    
    def __init__(self, result: Any, confirmed: bool = False, dialog_type: str = "unknown") -> None:
        super().__init__()
        self.result = result
        self.confirmed = confirmed
        self.dialog_type = dialog_type


class BaseDialog(Screen):
    """
    Базовый класс для всех диалоговых окон.
    Обеспечивает единообразный интерфейс и поведение.
    """
    
    def __init__(
        self,
        title: str = "",
        language_manager: Optional[LanguageManager] = None,
        dialog_type: str = "base",
        **kwargs
    ):
        """
        Инициализирует базовый диалог.
        
        Args:
            title: Заголовок диалога
            language_manager: Менеджер языков для локализации
            dialog_type: Тип диалога для различения результатов
        """
        super().__init__(**kwargs)
        self.title = title
        self.language_manager = language_manager
        self.dialog_type = dialog_type
        self._result: Any = None
        self._confirmed = False
        logger.debug(f"Создан диалог типа {dialog_type} с заголовком '{title}'")
        
    def get_text(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """Получает локализованный текст."""
        if self.language_manager:
            return self.language_manager.get_text(key, default, **kwargs)
        return default or key
        
    @abstractmethod
    def compose(self) -> Any:
        """Создает содержимое диалога."""
        pass
        
    def post_result(self, result: Any, confirmed: bool = False) -> None:
        """Отправляет результат диалога."""
        logger.debug(f"post_result вызван: result={result}, confirmed={confirmed}, dialog_type={self.dialog_type}")
        self._result = result
        self._confirmed = confirmed
        
        # Закрываем диалог с результатом
        logger.debug(f"Вызываем dismiss с результатом: {result}")
        self.dismiss(result)
        
    async def on_key(self, event: events.Key) -> None:
        """Обрабатывает клавиш по умолчанию."""
        logger.debug(f"BaseDialog on_key: {event.key} для диалога типа {self.dialog_type}")
        if event.key == "escape":
            logger.debug("BaseDialog: Escape нажат, отменяем диалог")
            await self.cancel()
            
    async def cancel(self) -> None:
        """Отменяет диалог."""
        logger.debug(f"Отменяем диалог типа {self.dialog_type}")
        self.dismiss(None)
        
    async def close(self) -> None:
        """Закрывает диалог."""
        self.dismiss(None)


class ConfirmDialog(BaseDialog):
    """
    Диалог подтверждения с кнопками Да/Нет/Отмена.
    """
    
    def __init__(
        self,
        message: str,
        title: str = "",
        yes_text: Optional[str] = None,
        no_text: Optional[str] = None,
        cancel_text: Optional[str] = None,
        show_cancel: bool = True,
        language_manager: Optional[LanguageManager] = None,
        dialog_type: str = "confirm",
        **kwargs
    ):
        """
        Инициализирует диалог подтверждения.
        
        Args:
            message: Текст сообщения
            title: Заголовок диалога
            yes_text: Текст кнопки "Да"
            no_text: Текст кнопки "Нет"
            cancel_text: Текст кнопки "Отмена"
            show_cancel: Показывать ли кнопку отмены
            language_manager: Менеджер языков
            dialog_type: Тип диалога
        """
        super().__init__(title, language_manager, dialog_type, **kwargs)
        self.message = message
        self.show_cancel = show_cancel
        
        # Инициализируем тексты кнопок
        self.yes_text = yes_text or self.get_text("yes", "Yes")
        self.no_text = no_text or self.get_text("no", "No")
        self.cancel_text = cancel_text or self.get_text("cancel", "Cancel")
        
        # Создаем кнопки
        self._btn_yes = Button(self.yes_text, id="yes", variant="primary")
        self._btn_no = Button(self.no_text, id="no", variant="default")
        self._btn_cancel = Button(self.cancel_text, id="cancel", variant="default") if show_cancel else None
        
        logger.debug(f"ConfirmDialog создан: message='{message[:50]}...', show_cancel={show_cancel}")

    def compose(self) -> Any:
        """Создает содержимое диалога подтверждения."""
        with Vertical(classes="dialog-content"):
            if self.title:
                yield Static(self.title, classes="dialog-title")
            yield Static(self.message, classes="dialog-message")
            
            # Создаем контейнер для кнопок
            buttons = [self._btn_yes, self._btn_no]
            if self._btn_cancel:
                buttons.append(self._btn_cancel)
                
            yield Horizontal(*buttons, classes="dialog-buttons")
            
            # Подсказка по горячим клавишам
            hint_parts = [f"Y - {self.yes_text}", f"N - {self.no_text}"]
            if self.show_cancel:
                hint_parts.append(f"Esc - {self.cancel_text}")
            hint = ", ".join(hint_parts)
            yield Static(hint, classes="dialog-hint")

    async def on_mount(self) -> None:
        """Устанавливает фокус на кнопку по умолчанию."""
        self._btn_yes.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обрабатывает нажатие кнопок."""
        button_id = event.button.id
        logger.debug(f"Нажата кнопка: {button_id}")
        
        if button_id == "yes":
            logger.debug("Отправляем результат 'yes'")
            self.post_result("yes", True)
        elif button_id == "no":
            logger.debug("Отправляем результат 'no'")
            self.post_result("no", True)
        elif button_id == "cancel":
            logger.debug("Отправляем результат 'cancel'")
            self.post_result("cancel", False)

    async def on_key(self, event: events.Key) -> None:
        """Обрабатывает горячие клавиши."""
        key = event.key.lower()
        logger.debug(f"Нажата клавиша в диалоге: {key}")
        
        if key == "y" or key == "enter":
            logger.debug("Отправляем результат 'yes' (клавиша)")
            self.post_result("yes", True)
            event.prevent_default()
            event.stop()
        elif key == "n":
            logger.debug("Отправляем результат 'no' (клавиша)")
            self.post_result("no", True)
            event.prevent_default()
            event.stop()
        elif key == "c" or key == "escape":
            logger.debug("Отправляем результат 'cancel' (клавиша)")
            self.post_result("cancel", False)
            event.prevent_default()
            event.stop()


class ConflictDialog(ConfirmDialog):
    """
    Специализированный диалог для разрешения конфликтов файлов.
    Добавляет горячую клавишу 'O' для Overwrite.
    """
    
    async def on_key(self, event: events.Key) -> None:
        """Обрабатывает горячие клавиши включая O для Overwrite."""
        key = event.key.lower()
        logger.debug(f"Нажата клавиша в конфликт-диалоге: {key}")
        
        if key == "y" or key == "o" or key == "enter":  # Y, O или Enter для подтверждения
            logger.debug("Отправляем результат 'yes' (конфликт-диалог)")
            self.post_result("yes", True)
            event.prevent_default()
            event.stop()
        elif key == "n" or key == "s":  # N или S для пропуска
            logger.debug("Отправляем результат 'no' (конфликт-диалог)")
            self.post_result("no", True)
            event.prevent_default()
            event.stop()
        elif key == "c" or key == "escape":  # C или Escape для отмены
            logger.debug("Отправляем результат 'cancel' (конфликт-диалог)")
            self.post_result("cancel", False)
            event.prevent_default()
            event.stop()


class InputDialog(BaseDialog):
    """
    Диалог ввода текста.
    """
    
    def __init__(
        self,
        prompt: str,
        title: str = "",
        default_value: str = "",
        placeholder: str = "",
        ok_text: Optional[str] = None,
        cancel_text: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
        language_manager: Optional[LanguageManager] = None,
        **kwargs
    ):
        """
        Инициализирует диалог ввода.
        
        Args:
            prompt: Текст приглашения
            title: Заголовок диалога
            default_value: Значение по умолчанию
            placeholder: Текст-заполнитель
            ok_text: Текст кнопки "OK"
            cancel_text: Текст кнопки "Отмена"
            validator: Функция валидации ввода
            language_manager: Менеджер языков
        """
        super().__init__(title, language_manager, dialog_type="input", **kwargs)
        self.prompt = prompt
        self.default_value = default_value
        self.placeholder = placeholder
        self.validator = validator
        
        # Инициализируем тексты кнопок
        self.ok_text = ok_text or self.get_text("ok", "OK")
        self.cancel_text = cancel_text or self.get_text("cancel", "Cancel")
        
        # Создаем элементы управления
        from textual.widgets import Input
        self._input = Input(
            value=default_value,
            placeholder=placeholder,
            id="input"
        )
        self._btn_ok = Button(self.ok_text, id="ok", variant="primary")
        self._btn_cancel = Button(self.cancel_text, id="cancel", variant="default")

    def compose(self) -> Any:
        """Создает содержимое диалога ввода."""
        with Vertical(classes="dialog-content"):
            if self.title:
                yield Static(self.title, classes="dialog-title")
            yield Static(self.prompt, classes="dialog-prompt")
            yield self._input
            yield Horizontal(self._btn_ok, self._btn_cancel, classes="dialog-buttons")

    async def on_mount(self) -> None:
        """Устанавливает фокус на поле ввода."""
        self._input.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обрабатывает нажатие кнопок."""
        button_id = event.button.id
        
        if button_id == "ok":
            value = self._input.value.strip()
            if self._validate_input(value):
                self.post_result(value, True)
        elif button_id == "cancel":
            self.post_result("", False)

    async def on_key(self, event: events.Key) -> None:
        """Обрабатывает горячие клавиши."""
        if event.key == "enter":
            value = self._input.value.strip()
            if self._validate_input(value):
                self.post_result(value, True)
                event.prevent_default()
                event.stop()
        elif event.key == "escape":
            self.post_result("", False)
            event.prevent_default()
            event.stop()

    def _validate_input(self, value: str) -> bool:
        """Валидирует введенное значение."""
        if self.validator:
            return self.validator(value)
        return len(value) > 0  # По умолчанию требуем непустое значение


class ProgressDialog(BaseDialog):
    """
    Диалог отображения прогресса операции.
    """
    
    def __init__(
        self,
        title: str = "",
        message: str = "",
        can_cancel: bool = True,
        language_manager: Optional[LanguageManager] = None,
        **kwargs
    ):
        """
        Инициализирует диалог прогресса.
        
        Args:
            title: Заголовок диалога
            message: Сообщение о выполняемой операции
            can_cancel: Можно ли отменить операцию
            language_manager: Менеджер языков
        """
        super().__init__(title, language_manager, dialog_type="progress", **kwargs)
        self.message = message
        self.can_cancel = can_cancel
        
        # Создаем элементы управления
        from textual.widgets import ProgressBar
        self._progress_bar = ProgressBar(total=100)
        self._status_text = Static("", classes="progress-status")
        
        cancel_text = self.get_text("cancel", "Cancel")
        self._btn_cancel = Button(cancel_text, id="cancel") if can_cancel else None

    def compose(self) -> Any:
        """Создает содержимое диалога прогресса."""
        with Vertical(classes="dialog-content"):
            if self.title:
                yield Static(self.title, classes="dialog-title")
            if self.message:
                yield Static(self.message, classes="dialog-message")
            yield self._progress_bar
            yield self._status_text
            if self._btn_cancel:
                yield Horizontal(self._btn_cancel, classes="dialog-buttons")

    def update_progress(self, progress: float, status: str = "") -> None:
        """
        Обновляет прогресс.
        
        Args:
            progress: Процент выполнения (0-100)
            status: Текст статуса
        """
        self._progress_bar.update(progress=progress)
        if status:
            self._status_text.update(status)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обрабатывает нажатие кнопки отмены."""
        if event.button.id == "cancel":
            self.post_result("cancel", False) 
"""
Модель конфигурации файлового менеджера.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional
import os


@dataclass
class PanelConfig:
    """
    Конфигурация панели файлов.
    
    Attributes:
        path: Путь к открытой директории
        show_hidden: Показывать ли скрытые файлы
        selected_index: Индекс выбранного элемента
        scroll_offset: Смещение прокрутки
    """
    path: Path = field(default_factory=lambda: Path.home())
    show_hidden: bool = False
    selected_index: int = 0
    scroll_offset: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь для сериализации."""
        return {
            'path': str(self.path),
            'show_hidden': self.show_hidden,
            'selected_index': self.selected_index,
            'scroll_offset': self.scroll_offset
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PanelConfig:
        """Создает экземпляр из словаря."""
        return cls(
            path=Path(data.get('path', str(Path.home()))),
            show_hidden=data.get('show_hidden', False),
            selected_index=data.get('selected_index', 0),
            scroll_offset=data.get('scroll_offset', 0)
        )


@dataclass
class AppConfig:
    """
    Общая конфигурация приложения.
    
    Attributes:
        left_panel: Конфигурация левой панели
        right_panel: Конфигурация правой панели
        active_panel: Активная панель ('left' или 'right')
        language: Код языка (например, 'ru', 'en')
        theme: Тема интерфейса
        window_size: Размер окна (ширина, высота)
    """
    left_panel: PanelConfig = field(default_factory=PanelConfig)
    right_panel: PanelConfig = field(default_factory=lambda: PanelConfig(path=Path.cwd()))
    active_panel: str = 'left'
    language: str = 'en'
    theme: str = 'monokai'
    window_size: tuple[int, int] = (120, 40)

    def __post_init__(self):
        """Валидация после инициализации."""
        if self.active_panel not in ('left', 'right'):
            self.active_panel = 'left'
        
        # Проверяем существование путей панелей
        if not self.left_panel.path.exists():
            self.left_panel.path = Path.home()
        if not self.right_panel.path.exists():
            self.right_panel.path = Path.cwd()

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь для сериализации."""
        return {
            'left_panel': self.left_panel.to_dict(),
            'right_panel': self.right_panel.to_dict(),
            'active_panel': self.active_panel,
            'language': self.language,
            'theme': self.theme,
            'window_size': list(self.window_size)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        """Создает экземпляр из словаря."""
        return cls(
            left_panel=PanelConfig.from_dict(data.get('left_panel', {})),
            right_panel=PanelConfig.from_dict(data.get('right_panel', {})),
            active_panel=data.get('active_panel', 'left'),
            language=data.get('language', 'en'),
            theme=data.get('theme', 'monokai'),
            window_size=tuple(data.get('window_size', [120, 40]))
        )

    def get_active_panel_config(self) -> PanelConfig:
        """Возвращает конфигурацию активной панели."""
        return self.left_panel if self.active_panel == 'left' else self.right_panel

    def get_inactive_panel_config(self) -> PanelConfig:
        """Возвращает конфигурацию неактивной панели."""
        return self.right_panel if self.active_panel == 'left' else self.left_panel

    def switch_active_panel(self) -> None:
        """Переключает активную панель."""
        self.active_panel = 'right' if self.active_panel == 'left' else 'left' 
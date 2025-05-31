"""
Модель элемента файловой системы (файл или папка).
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import os


@dataclass(frozen=True)
class FileItem:
    """
    Неизменяемая модель элемента файловой системы.
    
    Attributes:
        name: Имя файла или папки
        path: Полный путь к элементу
        is_dir: True если это папка, False если файл
        size: Размер в байтах (None для папок)
        modified_time: Время последнего изменения
        is_hidden: True если элемент скрытый
        extension: Расширение файла (пустая строка для папок)
        permissions: Права доступа в восьмеричном виде
    """
    name: str
    path: Path
    is_dir: bool
    size: Optional[int]
    modified_time: datetime
    is_hidden: bool
    extension: str = ""
    permissions: int = 0

    @classmethod
    def from_path(cls, path: Path) -> FileItem:
        """
        Создает FileItem из объекта Path.
        
        Args:
            path: Путь к файлу или папке
            
        Returns:
            FileItem: Новый экземпляр FileItem
            
        Raises:
            OSError: Если не удается получить информацию о файле
        """
        try:
            stat = path.stat()
            is_dir = path.is_dir()
            
            return cls(
                name=path.name,
                path=path.resolve(),
                is_dir=is_dir,
                size=None if is_dir else stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                is_hidden=path.name.startswith('.'),
                extension=path.suffix[1:] if path.suffix else "",
                permissions=stat.st_mode & 0o777
            )
        except OSError as e:
            raise OSError(f"Не удается получить информацию о файле {path}: {e}")

    def format_size(self) -> str:
        """
        Форматирует размер файла в читаемом виде.
        
        Returns:
            str: Отформатированный размер (например, "1.5 MB") или пустая строка для папок
        """
        if self.is_dir or self.size is None:
            return ""
            
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def format_date(self, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """
        Форматирует дату модификации.
        
        Args:
            format_str: Строка форматирования для strftime
            
        Returns:
            str: Отформатированная дата
        """
        return self.modified_time.strftime(format_str)

    def can_read(self) -> bool:
        """Проверяет, можно ли читать файл/папку."""
        return bool(self.permissions & 0o400)

    def can_write(self) -> bool:
        """Проверяет, можно ли писать в файл/папку."""
        return bool(self.permissions & 0o200)

    def can_execute(self) -> bool:
        """Проверяет, можно ли выполнить файл/войти в папку."""
        return bool(self.permissions & 0o100)

    def __str__(self) -> str:
        """Строковое представление для отладки."""
        return f"{'[DIR]' if self.is_dir else '[FILE]'} {self.name}" 
"""
Вспомогательные функции для файлового менеджера.
"""
import sys
import os
import subprocess
from pathlib import Path
from typing import Optional
from utils.constants import FILE_EXTENSIONS, FILE_TYPE_STYLES


def resource_path(relative_path: str) -> str:
    """
    Возвращает абсолютный путь к ресурсу.
    Работает как для PyInstaller, так и для обычного запуска.
    
    Args:
        relative_path: Относительный путь к ресурсу
        
    Returns:
        str: Абсолютный путь к ресурсу
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def get_file_type(file_extension: str) -> str:
    """
    Определяет тип файла по расширению.
    
    Args:
        file_extension: Расширение файла (с точкой)
        
    Returns:
        str: Тип файла для стилизации
    """
    extension = file_extension.lower()
    
    for file_type, extensions in FILE_EXTENSIONS.items():
        if extension in extensions:
            return file_type
    
    return 'default'


def get_file_style(file_type: str, is_hidden: bool = False, is_selected: bool = False, is_active: bool = False) -> str:
    """
    Возвращает стиль для файла на основе его типа и состояния.
    
    Args:
        file_type: Тип файла
        is_hidden: Является ли файл скрытым
        is_selected: Выделен ли файл
        is_active: Активен ли файл
        
    Returns:
        str: Строка стиля для rich
    """
    if is_selected:
        return FILE_TYPE_STYLES['selected']
    elif is_active:
        return FILE_TYPE_STYLES['active']
    elif is_hidden:
        return FILE_TYPE_STYLES['hidden']
    else:
        return FILE_TYPE_STYLES.get(file_type, '')


def open_file_external(file_path: Path) -> bool:
    """
    Открывает файл во внешнем приложении.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        bool: True если успешно открыт, False иначе
    """
    try:
        if sys.platform.startswith('darwin'):
            subprocess.Popen(['open', str(file_path)])
        elif sys.platform.startswith('win'):
            os.startfile(str(file_path))
        else:
            subprocess.Popen(['xdg-open', str(file_path)])
        return True
    except Exception:
        return False


def format_file_size(size_bytes: Optional[int]) -> str:
    """
    Форматирует размер файла в читаемом виде.
    
    Args:
        size_bytes: Размер в байтах
        
    Returns:
        str: Отформатированный размер
    """
    if size_bytes is None:
        return ""
        
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def is_text_file(file_path: Path, max_bytes: int = 8192) -> bool:
    """
    Проверяет, является ли файл текстовым.
    
    Args:
        file_path: Путь к файлу
        max_bytes: Максимальное количество байт для проверки
        
    Returns:
        bool: True если файл текстовый
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(max_bytes)
            
        # Проверяем на наличие нулевых байтов
        if b'\x00' in chunk:
            return False
            
        # Пытаемся декодировать как UTF-8
        try:
            chunk.decode('utf-8')
            return True
        except UnicodeDecodeError:
            pass
            
        # Пытаемся декодировать как latin-1
        try:
            chunk.decode('latin-1')
            return True
        except UnicodeDecodeError:
            return False
            
    except Exception:
        return False


def safe_path_join(base_path: Path, *paths: str) -> Optional[Path]:
    """
    Безопасно объединяет пути, предотвращая выход за пределы базового пути.
    
    Args:
        base_path: Базовый путь
        paths: Дополнительные компоненты пути
        
    Returns:
        Path: Безопасный путь или None если выход за пределы
    """
    try:
        result_path = base_path
        for path in paths:
            result_path = result_path / path
        
        # Проверяем, что результирующий путь находится в пределах базового
        result_resolved = result_path.resolve()
        base_resolved = base_path.resolve()
        
        if str(result_resolved).startswith(str(base_resolved)):
            return result_resolved
        else:
            return None
            
    except Exception:
        return None


def validate_filename(filename: str) -> bool:
    """
    Проверяет, является ли имя файла допустимым.
    
    Args:
        filename: Имя файла для проверки
        
    Returns:
        bool: True если имя допустимо
    """
    if not filename or filename in ('.', '..'):
        return False
        
    # Запрещенные символы в Windows и других ОС
    forbidden_chars = '<>:"/\\|?*'
    if any(char in filename for char in forbidden_chars):
        return False
        
    # Запрещенные имена в Windows
    forbidden_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    if filename.upper() in forbidden_names:
        return False
        
    return True 
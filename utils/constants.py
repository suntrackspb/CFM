"""
Константы для файлового менеджера.
"""
from pathlib import Path

# Пути
APP_NAME = "CFM"
CONFIG_FILENAME = "config.json"
THEME_FILENAME = "theme.css"
LANG_DIR = "lang"

# Файловые операции
CHUNK_SIZE = 1024 * 1024  # 1MB для копирования файлов
MAX_FILE_SIZE_FOR_PREVIEW = 10 * 1024 * 1024  # 10MB

# UI константы
MIN_PANEL_WIDTH = 20
DEFAULT_WINDOW_SIZE = (120, 40)
MAX_VISIBLE_ROWS = 100

# Горячие клавиши
KEY_BINDINGS = {
    'help': 'f1',
    'copy': 'f5',
    'move': 'f6',
    'mkdir': 'f7',
    'delete': 'f8',
    'toggle_hidden': 'f9',
    'switch_panel': 'tab',
    'select_all': 'ctrl+a',
    'refresh': 'f10',
    'quit': 'ctrl+q'
}

# Поддерживаемые языки
SUPPORTED_LANGUAGES = ['en', 'ru']
DEFAULT_LANGUAGE = 'en'

# Стили для различных типов файлов
FILE_TYPE_STYLES = {
    'directory': 'bold blue',
    'executable': 'bold green',
    'archive': 'bold red',
    'image': 'bold magenta',
    'video': 'bold cyan',
    'audio': 'bold yellow',
    'document': 'bold white',
    'code': 'bright_blue',
    'hidden': 'dim',
    'selected': 'on #66d9ef bold black',
    'active': 'on #49483e'
}

# Расширения файлов по категориям
FILE_EXTENSIONS = {
    'executable': {'.exe', '.bat', '.cmd', '.sh', '.bin', '.run', '.app'},
    'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.dmg', '.iso'},
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.tiff', '.webp'},
    'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'},
    'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'},
    'document': {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'},
    'code': {'.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.sql', '.php', '.java', '.cpp', '.c', '.h'}
}

# Конфигурация по умолчанию
DEFAULT_CONFIG = {
    'left_panel': {
        'path': str(Path.home()),
        'show_hidden': False,
        'selected_index': 0,
        'scroll_offset': 0
    },
    'right_panel': {
        'path': str(Path.cwd()),
        'show_hidden': False,
        'selected_index': 0,
        'scroll_offset': 0
    },
    'active_panel': 'left',
    'language': DEFAULT_LANGUAGE,
    'theme': 'monokai',
    'window_size': DEFAULT_WINDOW_SIZE
} 
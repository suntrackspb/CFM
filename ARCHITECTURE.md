# Архитектура файлового менеджера CFM

## Обзор

Проект был полностью рефакторинг с монолитной структуры на модульную архитектуру, основанную на принципах SOLID и чистой архитектуры.

## Структура проекта

```
CFM/
├── core/                           # Основная бизнес-логика
│   ├── __init__.py
│   ├── config_manager.py          # Управление конфигурацией
│   ├── language_manager.py        # Управление локализацией
│   └── file_operations.py         # Файловые операции
├── models/                         # Модели данных
│   ├── __init__.py
│   ├── file_item.py              # Модель файла/папки
│   └── config.py                 # Модель конфигурации
├── ui/                            # Пользовательский интерфейс
│   ├── __init__.py
│   ├── app_ui.py                 # Основной UI
│   ├── panels/                   # Панели файлов
│   │   ├── __init__.py
│   │   └── file_panel.py
│   └── dialogs/                  # Диалоговые окна
│       ├── __init__.py
│       └── base.py
├── utils/                         # Утилиты и helpers
│   ├── __init__.py
│   ├── constants.py              # Константы
│   └── helpers.py                # Вспомогательные функции
├── lang/                          # Языковые файлы
│   ├── en.json
│   └── ru.json
├── main.py                         # Основной файл запуска
├── config.json                    # Конфигурация
├── theme.css                      # Стили
└── requirements.txt
```

## Принципы архитектуры

### 1. Разделение ответственности (Single Responsibility Principle)

Каждый класс отвечает за одну конкретную задачу:
- **ConfigManager** — только управление конфигурацией
- **LanguageManager** — только локализация
- **FileOperationsManager** — только файловые операции
- **FileItem** — только представление файла/папки

### 2. Открыт для расширения, закрыт для модификации (Open/Closed Principle)

- Абстрактный класс `ConflictResolver` позволяет легко добавлять новые способы разрешения конфликтов
- Базовый класс `BaseDialog` упрощает создание новых диалогов
- Система плагинов для расширения функциональности

### 3. Принцип подстановки Лисков (Liskov Substitution Principle)

- Все диалоги наследуют от `BaseDialog` и взаимозаменяемы
- Различные реализации `ConflictResolver` работают одинаково

### 4. Принцип разделения интерфейсов (Interface Segregation Principle)

- Интерфейсы разбиты на специализированные части
- Клиенты зависят только от нужных им методов

### 5. Принцип инверсии зависимостей (Dependency Inversion Principle)

- Высокоуровневые модули не зависят от низкоуровневых
- Зависимости инъектируются через конструкторы
- Использование абстракций вместо конкретных реализаций

## Ключевые компоненты

### Core Layer (Ядро)

#### ConfigManager
```python
class ConfigManager:
    """Менеджер конфигурации с автосохранением и валидацией."""
    def load_config() -> AppConfig
    def save_config() -> bool
    def update_config(**kwargs) -> None
    def backup_config() -> bool
```

#### LanguageManager
```python
class LanguageManager:
    """Менеджер локализации с fallback и валидацией."""
    def load_language(code: str) -> bool
    def set_language(code: str) -> bool
    def get_text(key: str, **kwargs) -> str
    def validate_language_file(code: str) -> Dict
```

#### FileOperationsManager
```python
class FileOperationsManager:
    """Менеджер файловых операций с прогрессом и конфликтами."""
    def copy_items(items: List[FileItem], dest: Path) -> List[OperationItem]
    def move_items(items: List[FileItem], dest: Path) -> List[OperationItem]
    def delete_items(items: List[FileItem]) -> List[OperationItem]
    def create_directory(path: Path, name: str) -> OperationItem
```

### Models Layer (Модели)

#### FileItem
```python
@dataclass(frozen=True)
class FileItem:
    """Неизменяемая модель файла/папки."""
    name: str
    path: Path
    is_dir: bool
    size: Optional[int]
    modified_time: datetime
    is_hidden: bool
```

#### AppConfig
```python
@dataclass
class AppConfig:
    """Конфигурация приложения с валидацией."""
    left_panel: PanelConfig
    right_panel: PanelConfig
    active_panel: str
    language: str
    theme: str
```

### UI Layer (Интерфейс)

#### BaseDialog
```python
class BaseDialog(Widget, ABC):
    """Базовый класс для диалогов с локализацией."""
    @abstractmethod
    def compose() -> Any
    def post_result(result: Any, confirmed: bool) -> None
```

#### FileManagerUI
```python
class FileManagerUI(Widget):
    """Основной UI с панелями и логикой взаимодействия."""
    def initialize() -> None
    def copy_selected() -> None
    def move_selected() -> None
    def delete_selected() -> None
```

## Преимущества новой архитектуры

### 1. Масштабируемость
- Легко добавлять новые типы операций
- Простое расширение UI компонентов
- Возможность добавления плагинов

### 2. Тестируемость
- Каждый компонент можно тестировать изолированно
- Мокинг зависимостей через интерфейсы
- Единичные тесты для бизнес-логики

### 3. Сопровождаемость
- Четкое разделение ответственности
- Слабая связанность компонентов
- Понятная структура кода

### 4. Переиспользование
- Компоненты можно использовать в других проектах
- Базовые классы упрощают создание новых компонентов

### 5. Расширяемость
- Новые языки добавляются простым созданием JSON файла
- Новые темы через CSS файлы
- Новые типы диалогов через наследование

## Паттерны проектирования

### 1. Manager Pattern
- **ConfigManager**, **LanguageManager**, **FileOperationsManager**
- Централизованное управление ресурсами

### 2. Strategy Pattern
- **ConflictResolver** — различные стратегии разрешения конфликтов
- Возможность выбора алгоритма во время выполнения

### 3. Template Method Pattern
- **BaseDialog** — общий алгоритм работы диалогов
- Специализация в подклассах

### 4. Observer Pattern
- Колбэки для отслеживания прогресса операций
- События диалогов

### 5. Factory Pattern (потенциальный)
- Создание диалогов разных типов
- Создание панелей файлов

## Миграция с старой версии

### 1. Совместимость
- Старые файлы конфигурации автоматически конвертируются
- Языковые файлы остаются совместимыми
- CSS файлы работают без изменений

### 2. Поэтапный переход
- Запуск: `python main_new.py` для новой версии
- Откат: `python main.py` для старой версии
- Постепенная миграция функций

### 3. Тестирование
- Параллельное тестирование обеих версий
- Проверка функциональности на реальных данных

## Дальнейшее развитие

### 1. Планы на будущее
- Добавление системы плагинов
- Расширенные операции с файлами (архивация, шифрование)
- Сетевые операции (FTP, SFTP)
- Интеграция с облачными хранилищами

### 2. Улучшения UI
- Вкладки для множественных местоположений
- Предварительный просмотр файлов
- Кастомизируемые панели инструментов

### 3. Производительность
- Асинхронная загрузка больших директорий
- Кэширование метаданных файлов
- Оптимизация операций с большими файлами

## Заключение

Новая архитектура обеспечивает:
- **Четкое разделение ответственности** между компонентами
- **Высокую тестируемость** всех частей системы
- **Легкую расширяемость** для новых функций
- **Хорошую сопровождаемость** кода

Это создает прочную основу для дальнейшего развития файлового менеджера. 
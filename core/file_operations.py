"""
Менеджер файловых операций для файлового менеджера.
"""
import shutil
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Callable, Any, Generator
from models.file_item import FileItem
from utils.constants import CHUNK_SIZE
from utils.helpers import validate_filename

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Типы файловых операций."""
    COPY = "copy"
    MOVE = "move"
    DELETE = "delete"
    CREATE_DIR = "create_dir"


class OperationResult(Enum):
    """Результаты выполнения операций."""
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class OperationProgress:
    """Прогресс выполнения операции."""
    current_item: int
    total_items: int
    current_bytes: int
    total_bytes: int
    current_file: str
    operation_type: OperationType
    
    @property
    def progress_percent(self) -> float:
        """Процент выполнения по количеству элементов."""
        if self.total_items == 0:
            return 100.0
        return (self.current_item / self.total_items) * 100
        
    @property
    def bytes_percent(self) -> float:
        """Процент выполнения по объему данных."""
        if self.total_bytes == 0:
            return 100.0
        return (self.current_bytes / self.total_bytes) * 100


@dataclass
class OperationItem:
    """Элемент операции."""
    source: Path
    destination: Path
    operation_type: OperationType
    result: Optional[OperationResult] = None
    error_message: Optional[str] = None


class FileOperationError(Exception):
    """Исключение для ошибок файловых операций."""
    pass


class ConflictResolver(ABC):
    """Абстрактный класс для разрешения конфликтов."""
    
    @abstractmethod
    async def resolve_conflict(self, source: Path, destination: Path, operation_type: OperationType) -> str:
        """
        Разрешает конфликт при выполнении операции.
        
        Args:
            source: Исходный путь
            destination: Целевой путь
            operation_type: Тип операции
            
        Returns:
            str: 'overwrite', 'skip', 'rename', 'cancel'
        """
        pass


class FileOperationsManager:
    """
    Менеджер для выполнения файловых операций.
    Поддерживает пакетные операции, отслеживание прогресса и разрешение конфликтов.
    """
    
    def __init__(self, conflict_resolver: Optional[ConflictResolver] = None):
        """
        Инициализирует менеджер файловых операций.
        
        Args:
            conflict_resolver: Объект для разрешения конфликтов
        """
        self.conflict_resolver = conflict_resolver
        self._cancelled = False
        self._progress_callback: Optional[Callable[[OperationProgress], None]] = None

    def set_progress_callback(self, callback: Callable[[OperationProgress], None]) -> None:
        """Устанавливает колбэк для отслеживания прогресса."""
        self._progress_callback = callback

    def cancel_operation(self) -> None:
        """Отменяет текущую операцию."""
        self._cancelled = True
        logger.info("Операция отменена пользователем")

    async def copy_items(
        self, 
        items: List[FileItem], 
        destination_dir: Path,
        preserve_structure: bool = True
    ) -> List[OperationItem]:
        """
        Копирует список элементов в целевую директорию.
        
        Args:
            items: Список элементов для копирования
            destination_dir: Целевая директория
            preserve_structure: Сохранять ли структуру папок
            
        Returns:
            List[OperationItem]: Результаты операций
        """
        return await self._execute_batch_operation(
            items, destination_dir, OperationType.COPY, preserve_structure
        )

    async def move_items(
        self, 
        items: List[FileItem], 
        destination_dir: Path,
        preserve_structure: bool = True
    ) -> List[OperationItem]:
        """
        Перемещает список элементов в целевую директорию.
        
        Args:
            items: Список элементов для перемещения
            destination_dir: Целевая директория
            preserve_structure: Сохранять ли структуру папок
            
        Returns:
            List[OperationItem]: Результаты операций
        """
        return await self._execute_batch_operation(
            items, destination_dir, OperationType.MOVE, preserve_structure
        )

    async def delete_items(self, items: List[FileItem]) -> List[OperationItem]:
        """
        Удаляет список элементов.
        
        Args:
            items: Список элементов для удаления
            
        Returns:
            List[OperationItem]: Результаты операций
        """
        results = []
        total_items = len(items)
        
        self._cancelled = False
        
        for i, item in enumerate(items):
            if self._cancelled:
                break
                
            progress = OperationProgress(
                current_item=i + 1,
                total_items=total_items,
                current_bytes=0,
                total_bytes=0,
                current_file=str(item.path),
                operation_type=OperationType.DELETE
            )
            
            if self._progress_callback:
                self._progress_callback(progress)
                
            operation_item = OperationItem(
                source=item.path,
                destination=Path(),  # Для удаления destination не нужен
                operation_type=OperationType.DELETE
            )
            
            try:
                await self._delete_single_item(item.path)
                operation_item.result = OperationResult.SUCCESS
                logger.info(f"Удален: {item.path}")
                
            except FileOperationError as e:
                operation_item.result = OperationResult.ERROR
                operation_item.error_message = str(e)
                logger.error(f"Ошибка удаления {item.path}: {e}")
                
            results.append(operation_item)
            
        return results

    async def create_directory(self, path: Path, name: str) -> OperationItem:
        """
        Создает новую директорию.
        
        Args:
            path: Путь где создать директорию
            name: Имя новой директории
            
        Returns:
            OperationItem: Результат операции
        """
        if not validate_filename(name):
            raise FileOperationError(f"Недопустимое имя директории: {name}")
            
        new_dir_path = path / name
        
        operation_item = OperationItem(
            source=Path(),
            destination=new_dir_path,
            operation_type=OperationType.CREATE_DIR
        )
        
        try:
            new_dir_path.mkdir(parents=True, exist_ok=False)
            operation_item.result = OperationResult.SUCCESS
            logger.info(f"Создана директория: {new_dir_path}")
            
        except FileExistsError:
            operation_item.result = OperationResult.ERROR
            operation_item.error_message = "Директория уже существует"
            
        except Exception as e:
            operation_item.result = OperationResult.ERROR
            operation_item.error_message = str(e)
            logger.error(f"Ошибка создания директории {new_dir_path}: {e}")
            
        return operation_item

    async def _execute_batch_operation(
        self,
        items: List[FileItem],
        destination_dir: Path,
        operation_type: OperationType,
        preserve_structure: bool
    ) -> List[OperationItem]:
        """Выполняет пакетную операцию над элементами."""
        results = []
        total_items = len(items)
        total_bytes = sum(item.size or 0 for item in items if not item.is_dir)
        current_bytes = 0
        
        self._cancelled = False
        
        for i, item in enumerate(items):
            if self._cancelled:
                break
                
            progress = OperationProgress(
                current_item=i + 1,
                total_items=total_items,
                current_bytes=current_bytes,
                total_bytes=total_bytes,
                current_file=str(item.path),
                operation_type=operation_type
            )
            
            if self._progress_callback:
                self._progress_callback(progress)
                
            destination = destination_dir / item.name
            
            operation_item = OperationItem(
                source=item.path,
                destination=destination,
                operation_type=operation_type
            )
            
            try:
                # Проверяем конфликты
                if destination.exists():
                    if self.conflict_resolver:
                        resolution = await self.conflict_resolver.resolve_conflict(
                            item.path, destination, operation_type
                        )
                        
                        if resolution == 'cancel':
                            self._cancelled = True
                            break
                        elif resolution == 'skip':
                            operation_item.result = OperationResult.SKIPPED
                            results.append(operation_item)
                            continue
                        elif resolution == 'rename':
                            destination = self._get_unique_name(destination)
                            operation_item.destination = destination
                            
                # Выполняем операцию
                if operation_type == OperationType.COPY:
                    await self._copy_single_item(item.path, destination)
                elif operation_type == OperationType.MOVE:
                    await self._move_single_item(item.path, destination)
                    
                operation_item.result = OperationResult.SUCCESS
                
                if not item.is_dir and item.size:
                    current_bytes += item.size
                    
                logger.info(f"{operation_type.value.capitalize()}: {item.path} -> {destination}")
                
            except FileOperationError as e:
                operation_item.result = OperationResult.ERROR
                operation_item.error_message = str(e)
                logger.error(f"Ошибка {operation_type.value} {item.path}: {e}")
                
            results.append(operation_item)
            
        return results

    async def _copy_single_item(self, source: Path, destination: Path) -> None:
        """Копирует отдельный элемент."""
        try:
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                # Копируем файл с сохранением метаданных
                shutil.copy2(source, destination)
        except Exception as e:
            raise FileOperationError(f"Ошибка копирования {source}: {e}")

    async def _move_single_item(self, source: Path, destination: Path) -> None:
        """Перемещает отдельный элемент."""
        try:
            shutil.move(source, destination)
        except Exception as e:
            raise FileOperationError(f"Ошибка перемещения {source}: {e}")

    async def _delete_single_item(self, path: Path) -> None:
        """Удаляет отдельный элемент."""
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except Exception as e:
            raise FileOperationError(f"Ошибка удаления {path}: {e}")

    def _get_unique_name(self, path: Path) -> Path:
        """Генерирует уникальное имя для файла/папки."""
        counter = 1
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        
        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

    def calculate_operation_size(self, items: List[FileItem]) -> int:
        """
        Вычисляет общий размер операции.
        
        Args:
            items: Список элементов
            
        Returns:
            int: Общий размер в байтах
        """
        total_size = 0
        
        for item in items:
            if item.is_dir:
                # Для директорий рекурсивно подсчитываем размер
                try:
                    for file_path in item.path.rglob('*'):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                except Exception:
                    pass  # Игнорируем ошибки доступа
            else:
                total_size += item.size or 0
                
        return total_size 
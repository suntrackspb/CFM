"""
Менеджер конфигурации для файлового менеджера.
"""
import json
import logging
from pathlib import Path
from typing import Optional
from models.config import AppConfig
from utils.constants import CONFIG_FILENAME, DEFAULT_CONFIG
from utils.helpers import resource_path

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Менеджер для работы с конфигурацией приложения.
    Обеспечивает загрузку, сохранение и валидацию настроек.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Инициализирует менеджер конфигурации.
        
        Args:
            config_path: Путь к файлу конфигурации. Если None, используется значение по умолчанию.
        """
        if config_path is None:
            self.config_path = Path(resource_path(CONFIG_FILENAME))
        else:
            self.config_path = config_path
            
        self._config: Optional[AppConfig] = None

    def load_config(self) -> AppConfig:
        """
        Загружает конфигурацию из файла.
        Если файл не существует или поврежден, создает конфигурацию по умолчанию.
        
        Returns:
            AppConfig: Загруженная или созданная конфигурация
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                logger.debug(f"Загружены данные конфигурации: {type(data)} = {data}")
                self._config = AppConfig.from_dict(data)
                logger.info(f"Конфигурация загружена из {self.config_path}")
            else:
                logger.info("Файл конфигурации не найден, создаю новый")
                self._config = AppConfig.from_dict(DEFAULT_CONFIG)
                self.save_config()
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Ошибка загрузки конфигурации: {e}. Используется конфигурация по умолчанию")
            self._config = AppConfig.from_dict(DEFAULT_CONFIG)
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке конфигурации: {e}")
            self._config = AppConfig.from_dict(DEFAULT_CONFIG)
            
        return self._config

    def save_config(self) -> bool:
        """
        Сохраняет текущую конфигурацию в файл.
        
        Returns:
            bool: True если сохранение успешно, False иначе
        """
        if self._config is None:
            logger.warning("Попытка сохранить несуществующую конфигурацию")
            return False
            
        try:
            # Создаем директорию если не существует
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
                
            logger.info(f"Конфигурация сохранена в {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False

    def get_config(self) -> AppConfig:
        """
        Возвращает текущую конфигурацию.
        Если конфигурация не загружена, загружает её.
        
        Returns:
            AppConfig: Текущая конфигурация
        """
        if self._config is None:
            self.load_config()
        return self._config

    def update_config(self, **kwargs) -> None:
        """
        Обновляет конфигурацию и сохраняет изменения.
        
        Args:
            **kwargs: Атрибуты конфигурации для обновления
        """
        if self._config is None:
            self.load_config()
            
        # Обновляем атрибуты конфигурации
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                logger.warning(f"Неизвестный атрибут конфигурации: {key}")
                
        # Валидируем обновленную конфигурацию
        self._config.__post_init__()
        
        # Сохраняем изменения
        self.save_config()

    def reset_to_defaults(self) -> None:
        """Сбрасывает конфигурацию к значениям по умолчанию."""
        self._config = AppConfig.from_dict(DEFAULT_CONFIG)
        self.save_config()
        logger.info("Конфигурация сброшена к значениям по умолчанию")

    def backup_config(self, backup_path: Optional[Path] = None) -> bool:
        """
        Создает резервную копию конфигурации.
        
        Args:
            backup_path: Путь для резервной копии. Если None, создается рядом с основным файлом.
            
        Returns:
            bool: True если резервная копия создана успешно
        """
        if backup_path is None:
            backup_path = self.config_path.with_suffix('.bak')
            
        try:
            if self.config_path.exists():
                import shutil
                shutil.copy2(self.config_path, backup_path)
                logger.info(f"Резервная копия конфигурации создана: {backup_path}")
                return True
            else:
                logger.warning("Файл конфигурации не существует, резервная копия не создана")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка создания резервной копии: {e}")
            return False

    def restore_from_backup(self, backup_path: Optional[Path] = None) -> bool:
        """
        Восстанавливает конфигурацию из резервной копии.
        
        Args:
            backup_path: Путь к резервной копии. Если None, ищет рядом с основным файлом.
            
        Returns:
            bool: True если восстановление успешно
        """
        if backup_path is None:
            backup_path = self.config_path.with_suffix('.bak')
            
        try:
            if backup_path.exists():
                import shutil
                shutil.copy2(backup_path, self.config_path)
                self._config = None  # Заставляем перезагрузить конфигурацию
                self.load_config()
                logger.info(f"Конфигурация восстановлена из резервной копии: {backup_path}")
                return True
            else:
                logger.warning("Резервная копия не найдена")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка восстановления из резервной копии: {e}")
            return False 
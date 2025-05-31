"""
Тесты для ConfigManager.
"""
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from core.config_manager import ConfigManager
from models.config import AppConfig, PanelConfig
from utils.constants import DEFAULT_CONFIG


class TestConfigManager:
    """Тесты для класса ConfigManager."""
    
    def test_init_default_path(self):
        """Тест инициализации с путем по умолчанию."""
        manager = ConfigManager()
        assert manager.config_path.name == "config.json"
        
    def test_init_custom_path(self):
        """Тест инициализации с пользовательским путем."""
        custom_path = Path("/custom/config.json")
        manager = ConfigManager(custom_path)
        assert manager.config_path == custom_path
        
    def test_load_config_file_not_exists(self):
        """Тест загрузки конфигурации когда файл не существует."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "nonexistent.json"
            manager = ConfigManager(config_path)
            
            config = manager.load_config()
            
            assert isinstance(config, AppConfig)
            assert config.language == 'en'  # значение по умолчанию
            assert config_path.exists()  # файл должен быть создан
            
    def test_load_config_valid_file(self):
        """Тест загрузки валидной конфигурации."""
        test_config = {
            'language': 'ru',
            'active_panel': 'right',
            'left_panel': {'path': str(Path.home())},
            'right_panel': {'path': str(Path.cwd())}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = Path(f.name)
            
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            assert config.language == 'ru'
            assert config.active_panel == 'right'
        finally:
            config_path.unlink()
            
    def test_load_config_invalid_json(self):
        """Тест загрузки поврежденного JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            config_path = Path(f.name)
            
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            # Должна загрузиться конфигурация по умолчанию
            assert isinstance(config, AppConfig)
            assert config.language == 'en'
        finally:
            config_path.unlink()
            
    def test_save_config_success(self):
        """Тест успешного сохранения конфигурации."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(config_path)
            
            # Загружаем конфигурацию по умолчанию
            config = manager.load_config()
            config.language = 'ru'
            
            # Сохраняем
            result = manager.save_config()
            
            assert result is True
            assert config_path.exists()
            
            # Проверяем содержимое
            with open(config_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            assert saved_data['language'] == 'ru'
            
    def test_save_config_no_config_loaded(self):
        """Тест сохранения когда конфигурация не загружена."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(config_path)
            
            # Не загружаем конфигурацию
            result = manager.save_config()
            
            assert result is False
            
    def test_update_config(self):
        """Тест обновления конфигурации."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(config_path)
            
            # Загружаем конфигурацию
            manager.load_config()
            
            # Обновляем
            manager.update_config(language='ru', active_panel='right')
            
            # Проверяем обновление
            config = manager.get_config()
            assert config.language == 'ru'
            assert config.active_panel == 'right'
            
    def test_update_config_invalid_attribute(self, caplog):
        """Тест обновления с неизвестным атрибутом."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(config_path)
            
            manager.load_config()
            manager.update_config(invalid_attr='value')
            
            assert "Неизвестный атрибут" in caplog.text
            
    def test_reset_to_defaults(self):
        """Тест сброса к настройкам по умолчанию."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(config_path)
            
            # Загружаем и изменяем конфигурацию
            config = manager.load_config()
            config.language = 'ru'
            manager.save_config()
            
            # Сбрасываем
            manager.reset_to_defaults()
            
            # Проверяем сброс
            config = manager.get_config()
            assert config.language == 'en'
            
    def test_backup_config(self):
        """Тест создания резервной копии."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            backup_path = Path(temp_dir) / "backup.json"
            manager = ConfigManager(config_path)
            
            # Создаем конфигурацию
            manager.load_config()
            manager.save_config()
            
            # Создаем резервную копию
            result = manager.backup_config(backup_path)
            
            assert result is True
            assert backup_path.exists()
            
    def test_restore_from_backup(self):
        """Тест восстановления из резервной копии."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"
            backup_path = Path(temp_dir) / "backup.json"
            manager = ConfigManager(config_path)
            
            # Создаем оригинальную конфигурацию
            config = manager.load_config()
            config.language = 'ru'
            manager.save_config()
            
            # Создаем резервную копию
            manager.backup_config(backup_path)
            
            # Изменяем оригинал
            config.language = 'en'
            manager.save_config()
            
            # Восстанавливаем из резервной копии
            result = manager.restore_from_backup(backup_path)
            
            assert result is True
            restored_config = manager.get_config()
            assert restored_config.language == 'ru'


@pytest.fixture
def temp_config_manager():
    """Фикстура для временного ConfigManager."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.json"
        yield ConfigManager(config_path) 
"""
Менеджер языков для файлового менеджера.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Set
from utils.constants import LANG_DIR, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from utils.helpers import resource_path

logger = logging.getLogger(__name__)


class LanguageManager:
    """
    Менеджер для работы с локализацией приложения.
    Обеспечивает загрузку языковых файлов и получение переводов.
    """
    
    def __init__(self, lang_dir: Optional[Path] = None):
        """
        Инициализирует менеджер языков.
        
        Args:
            lang_dir: Путь к директории с языковыми файлами. Если None, используется значение по умолчанию.
        """
        if lang_dir is None:
            self.lang_dir = Path(resource_path(LANG_DIR))
        else:
            self.lang_dir = lang_dir
            
        self._languages: Dict[str, Dict[str, str]] = {}
        self._current_language = DEFAULT_LANGUAGE
        self._fallback_language = DEFAULT_LANGUAGE

    def load_language(self, language_code: str) -> bool:
        """
        Загружает языковой файл.
        
        Args:
            language_code: Код языка (например, 'ru', 'en')
            
        Returns:
            bool: True если язык загружен успешно
        """
        lang_file = self.lang_dir / f"{language_code}.json"
        
        try:
            if not lang_file.exists():
                logger.warning(f"Языковой файл не найден: {lang_file}")
                return False
                
            with open(lang_file, 'r', encoding='utf-8') as f:
                self._languages[language_code] = json.load(f)
                
            logger.info(f"Язык {language_code} загружен успешно")
            return True
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Ошибка загрузки языкового файла {lang_file}: {e}")
            return False

    def load_all_languages(self) -> None:
        """Загружает все доступные языки."""
        for language_code in SUPPORTED_LANGUAGES:
            self.load_language(language_code)
            
        # Если текущий язык не загружен, используем язык по умолчанию
        if self._current_language not in self._languages:
            if DEFAULT_LANGUAGE in self._languages:
                self._current_language = DEFAULT_LANGUAGE
            elif self._languages:
                self._current_language = list(self._languages.keys())[0]

    def set_language(self, language_code: str) -> bool:
        """
        Устанавливает активный язык.
        
        Args:
            language_code: Код языка
            
        Returns:
            bool: True если язык установлен успешно
        """
        if language_code not in self._languages:
            if not self.load_language(language_code):
                logger.warning(f"Не удалось загрузить язык {language_code}")
                return False
                
        self._current_language = language_code
        logger.info(f"Активный язык изменен на {language_code}")
        return True

    def get_text(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        Получает переведенный текст по ключу.
        
        Args:
            key: Ключ перевода
            default: Значение по умолчанию, если перевод не найден
            **kwargs: Параметры для форматирования строки
            
        Returns:
            str: Переведенный текст
        """
        # Пытаемся найти перевод в текущем языке
        current_lang = self._languages.get(self._current_language, {})
        text = current_lang.get(key)
        
        # Если не найден, ищем в языке по умолчанию
        if text is None and self._current_language != self._fallback_language:
            fallback_lang = self._languages.get(self._fallback_language, {})
            text = fallback_lang.get(key)
            
        # Если все еще не найден, используем значение по умолчанию или сам ключ
        if text is None:
            text = default if default is not None else key
            logger.debug(f"Перевод не найден для ключа '{key}', используется '{text}'")
            
        # Форматируем строку с параметрами
        try:
            if kwargs:
                text = text.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"Ошибка форматирования строки '{text}' с параметрами {kwargs}: {e}")
            
        return text

    def get_current_language(self) -> str:
        """Возвращает код текущего языка."""
        return self._current_language

    def get_available_languages(self) -> Set[str]:
        """Возвращает множество доступных языков."""
        return set(self._languages.keys())

    def is_language_available(self, language_code: str) -> bool:
        """
        Проверяет, доступен ли язык.
        
        Args:
            language_code: Код языка
            
        Returns:
            bool: True если язык доступен
        """
        return language_code in self._languages

    def get_language_info(self, language_code: str) -> Optional[Dict[str, str]]:
        """
        Возвращает информацию о языке.
        
        Args:
            language_code: Код языка
            
        Returns:
            Dict с информацией о языке или None если язык не найден
        """
        if language_code not in self._languages:
            return None
            
        lang_data = self._languages[language_code]
        return {
            'code': language_code,
            'name': lang_data.get('language_name', language_code),
            'native_name': lang_data.get('language_native_name', language_code),
            'keys_count': len(lang_data)
        }

    def validate_language_file(self, language_code: str) -> Dict[str, any]:
        """
        Валидирует языковой файл на полноту переводов.
        
        Args:
            language_code: Код языка для проверки
            
        Returns:
            Dict с результатами валидации
        """
        if language_code not in self._languages:
            return {'valid': False, 'error': 'Язык не загружен'}
            
        if self._fallback_language not in self._languages:
            return {'valid': False, 'error': 'Базовый язык не загружен'}
            
        current_keys = set(self._languages[language_code].keys())
        fallback_keys = set(self._languages[self._fallback_language].keys())
        
        missing_keys = fallback_keys - current_keys
        extra_keys = current_keys - fallback_keys
        
        return {
            'valid': len(missing_keys) == 0,
            'missing_keys': list(missing_keys),
            'extra_keys': list(extra_keys),
            'coverage': len(current_keys & fallback_keys) / len(fallback_keys) if fallback_keys else 0
        }

    def __getitem__(self, key: str) -> str:
        """Позволяет использовать менеджер как словарь для получения переводов."""
        return self.get_text(key)

    def __contains__(self, key: str) -> bool:
        """Проверяет, существует ли перевод для ключа."""
        current_lang = self._languages.get(self._current_language, {})
        return key in current_lang 
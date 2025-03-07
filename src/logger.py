
"""Модуль для логирования событий приложения"""

import os
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
import threading
import json

from src.interfaces import ILogger

class Logger(ILogger):
    """
    Имплементация интерфейса логирования.
    Поддерживает вывод в консоль и файл с ротацией логов по дням.
    """
    
    def __init__(self, log_level: int = logging.INFO, log_dir: str = 'logs'):
        """
        Инициализация системы логирования.
        
        Args:
            log_level (int): Уровень детализации логов
            log_dir (str): Директория для хранения файлов логов
        """
        self.log_level = log_level
        self.log_dir = log_dir
        self.error_descriptions = self._load_error_descriptions()
        self.lock = threading.RLock()  # Для потокобезопасности
        
        # Создаем директорию для логов, если не существует
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Создаем и настраиваем логгер
        self.logger = logging.getLogger("bot_logger")
        self.logger.setLevel(self.log_level)
        
        # Очищаем обработчики логов, если они уже были настроены
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Настраиваем форматирование
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Создаем и настраиваем обработчик для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Создаем и настраиваем обработчик для записи в файл
        self.file_handler = None
        self._setup_file_handler()

        self.info("Система логирования инициализирована")
    
    def _setup_file_handler(self) -> None:
        """Настраивает обработчик для записи логов в файл с учетом текущей даты"""
        with self.lock:
            # Если обработчик для файла уже существует, удаляем его
            if self.file_handler and self.file_handler in self.logger.handlers:
                self.logger.removeHandler(self.file_handler)
            
            # Формируем имя файла для текущей даты
            current_date = datetime.now().strftime('%Y%m%d')
            log_filename = os.path.join(self.log_dir, f'bot_log_{current_date}.log')
            
            # Создаем и настраиваем новый обработчик
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            self.file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            self.file_handler.setLevel(self.log_level)
            self.file_handler.setFormatter(formatter)
            self.logger.addHandler(self.file_handler)
    
    def _check_log_rotation(self) -> None:
        """Проверяет необходимость ротации лог-файла по дате"""
        with self.lock:
            # Проверяем, соответствует ли текущий файл логов текущей дате
            current_date = datetime.now().strftime('%Y%m%d')
            
            if self.file_handler:
                # Извлекаем дату из имени текущего файла логов
                current_log_file = os.path.basename(self.file_handler.baseFilename)
                if f'bot_log_{current_date}.log' != current_log_file:
                    # Если даты не совпадают, настраиваем новый файл
                    self._setup_file_handler()
    
    def _load_error_descriptions(self) -> Dict[str, str]:
        """
        Загружает словарь с описаниями ошибок.
        
        Returns:
            Dict[str, str]: Словарь с описаниями ошибок
        """
        # Базовые описания ошибок
        descriptions = {
            "ConnectionError": "Ошибка подключения к внешнему API. Проверьте интернет-соединение.",
            "Timeout": "Превышено время ожидания ответа от внешнего API.",
            "JSONDecodeError": "Ошибка при разборе JSON ответа от API.",
            "HTTPError": "Ошибка HTTP при запросе к внешнему API.",
            "TelegramError": "Ошибка при взаимодействии с Telegram API.",
            "KeyboardInterrupt": "Бот был остановлен вручную.",
            "ApiError": "Ошибка при взаимодействии с внешним API.",
            "TelegramError": "Ошибка Telegram API",
            "Unauthorized": "Неверный токен бота",
            "BadRequest": "Неверный запрос к Telegram API",
            "TimedOut": "Превышено время ожидания ответа от Telegram API",
            "NetworkError": "Проблемы с сетью",
            "ChatMigrated": "Чат был перенесен",
            "RetryAfter": "Превышен лимит запросов, ожидание",
            "InvalidToken": "Неверный токен бота",
            "Conflict": "Конфликт запросов getUpdates. Проверьте, что запущен только один экземпляр бота"
        }
        
        return descriptions
    
    def info(self, message: str) -> None:
        """
        Логирование информационного сообщения.
        
        Args:
            message (str): Информационное сообщение
        """
        self._check_log_rotation()
        self.logger.info(message)
    
    def error(self, message: str) -> None:
        """
        Логирование сообщения об ошибке.
        
        Args:
            message (str): Сообщение об ошибке
        """
        self._check_log_rotation()
        self.logger.error(message)
    
    def warning(self, message: str) -> None:
        """
        Логирование предупреждения.
        
        Args:
            message (str): Предупреждающее сообщение
        """
        self._check_log_rotation()
        self.logger.warning(message)
    
    def debug(self, message: str) -> None:
        """
        Логирование отладочного сообщения.
        
        Args:
            message (str): Отладочное сообщение
        """
        self._check_log_rotation()
        self.logger.debug(message)
    
    def log_error(self, error: Exception, additional_info: Optional[Dict[str, Any]] = None) -> None:
        """
        Логирование исключения с дополнительной информацией.
        
        Args:
            error (Exception): Объект исключения
            additional_info (Dict[str, Any], optional): Дополнительная информация
        """
        self._check_log_rotation()
        
        # Получаем тип ошибки
        error_type = type(error).__name__
        
        # Получаем описание ошибки из словаря или используем сообщение ошибки
        error_description = self.error_descriptions.get(error_type, str(error))
        
        # Формируем сообщение об ошибке
        error_message = f"Ошибка [{error_type}]: {error_description}"
        
        # Добавляем дополнительную информацию, если она предоставлена
        if additional_info:
            info_str = json.dumps(additional_info, ensure_ascii=False, default=str)
            error_message += f" Дополнительная информация: {info_str}"
        
        # Логируем сообщение об ошибке
        self.logger.error(error_message)
        
        # Логируем стек вызовов
        self.logger.error(f"Стек вызовов:\n{traceback.format_exc()}")
    
    def get_logs(self, level: Optional[str] = None, 
                 start_date: Optional[datetime] = None, 
                 end_date: Optional[datetime] = None, 
                 limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение логов с фильтрацией по уровню, дате и ограничением количества.
        
        Args:
            level (str, optional): Уровень логирования для фильтрации
            start_date (datetime, optional): Начальная дата для фильтрации
            end_date (datetime, optional): Конечная дата для фильтрации
            limit (int): Максимальное количество возвращаемых записей
            
        Returns:
            List[Dict[str, Any]]: Список записей логов
        """
        logs = []
        
        # Определяем период для поиска логов
        if not start_date:
            # Если начальная дата не указана, берем логи только за текущий день
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if not end_date:
            # Если конечная дата не указана, берем до текущего момента
            end_date = datetime.now()
        
        # Преобразуем уровень логирования в числовое значение
        level_num = None
        if level:
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL
            }
            level_num = level_map.get(level.upper())
        
        # Получаем список файлов логов в заданном периоде
        log_files = []
        current_date = start_date
        while current_date <= end_date:
            log_filename = os.path.join(self.log_dir, f'bot_log_{current_date.strftime("%Y%m%d")}.log')
            if os.path.exists(log_filename):
                log_files.append(log_filename)
            
            # Переходим к следующему дню
            current_date = current_date.replace(day=current_date.day + 1)
        
        # Обрабатываем файлы логов в обратном порядке (от новых к старым)
        for log_file in reversed(log_files):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in reversed(f.readlines()):
                        try:
                            # Разбираем строку лога
                            parts = line.strip().split(' - ', 2)
                            if len(parts) < 3:
                                continue
                            
                            timestamp_str, log_level, message = parts
                            
                            # Парсим временную метку
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            
                            # Проверяем, входит ли запись в указанный период
                            if timestamp < start_date or timestamp > end_date:
                                continue
                            
                            # Проверяем, соответствует ли запись указанному уровню
                            if level_num is not None:
                                current_level_num = {
                                    "DEBUG": logging.DEBUG,
                                    "INFO": logging.INFO,
                                    "WARNING": logging.WARNING,
                                    "ERROR": logging.ERROR,
                                    "CRITICAL": logging.CRITICAL
                                }.get(log_level)
                                
                                if current_level_num is None or current_level_num < level_num:
                                    continue
                            
                            # Добавляем запись в результат
                            logs.append({
                                "timestamp": timestamp,
                                "level": log_level,
                                "message": message
                            })
                            
                            # Проверяем ограничение на количество
                            if len(logs) >= limit:
                                break
                        except Exception:
                            # Пропускаем некорректные строки
                            continue
                
                # Если достигнуто ограничение, прекращаем обработку файлов
                if len(logs) >= limit:
                    break
                    
            except Exception as e:
                self.error(f"Ошибка при чтении файла логов {log_file}: {e}")
        
        return logs

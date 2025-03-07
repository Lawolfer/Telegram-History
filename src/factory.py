
"""Фабрика для создания компонентов бота"""

from typing import Dict, Any

from src.api_client import APIClient
from src.api_cache import APICache
from src.logger import Logger
from src.content_service import ContentService
from src.ui_manager import UIManager
from src.message_manager import MessageManager
from src.state_manager import StateManager
from src.admin_panel import AdminPanel
from src.handlers import CommandHandlers
from src.bot import Bot
from src.analytics import AnalyticsService
from src.history_map import HistoryMap
from src.web_server import WebServer

class BotFactory:
    """
    Фабрика для создания объектов бота.
    Реализует паттерн Factory для создания и инициализации компонентов системы.
    """
    
    @staticmethod
    def create_bot(config):
        """
        Создает экземпляр бота и все необходимые компоненты.
        
        Args:
            config: Конфигурация приложения
            
        Returns:
            Bot: Настроенный экземпляр бота
        """
        # Создаем логгер
        logger = Logger()
        logger.info("Инициализация компонентов бота")
        
        # Создаем кэш для API
        api_cache = APICache(logger, max_size=100, cache_file='api_cache.json')
        
        # Создаем API-клиент
        api_client = APIClient(config.gemini_api_key, api_cache, logger)
        
        # Создаем менеджер состояний
        state_manager = StateManager(logger)
        
        # Создаем менеджер сообщений
        message_manager = MessageManager(logger)
        
        # Создаем UI-менеджер
        ui_manager = UIManager(logger)
        
        # Создаем сервис контента
        content_service = ContentService(api_client, logger)
        
        # Создаем аналитический сервис
        analytics_service = AnalyticsService(logger)
        
        # Создаем сервис исторических карт
        history_map_service = HistoryMap(logger)
        
        # Создаем админ-панель
        admin_panel = AdminPanel(logger, config)
        
        # Создаем обработчик команд
        command_handlers = CommandHandlers(
            ui_manager=ui_manager,
            api_client=api_client,
            message_manager=message_manager,
            content_service=content_service,
            logger=logger,
            config=config
        )
        
        # Создаем веб-сервер
        web_server = WebServer(
            logger=logger,
            analytics_service=analytics_service,
            admin_panel=admin_panel,
            history_map_service=history_map_service
        )
        
        # Создаем бота
        bot = Bot(
            config=config,
            logger=logger,
            command_handlers=command_handlers,
            state_manager=state_manager,
            analytics_service=analytics_service,
            web_server=web_server
        )
        
        logger.info("Все компоненты бота инициализированы успешно")
        
        return bot

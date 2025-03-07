
import threading
import time
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.telegram_queue import TelegramRequestQueue

class MessageManager:
    """Класс для управления сообщениями с оптимизированными запросами к Telegram API"""

    def __init__(self, logger):
        self.logger = logger
        self.active_messages = {}  # Кэш активных сообщений по user_id
        self.message_lock = threading.RLock()  # Блокировка для потокобезопасного доступа
        self.request_queue = TelegramRequestQueue(max_requests_per_second=25, logger=logger)

    def save_message_id(self, update, context, message_id):
        """
        Сохраняет ID сообщения с оптимизацией.

        Args:
            update (telegram.Update): Объект обновления Telegram
            context (telegram.ext.CallbackContext): Контекст разговора
            message_id (int): ID сообщения для сохранения
        """
        # Получаем user_id
        user_id = update.effective_user.id

        # Используем блокировку для потокобезопасной работы
        with self.message_lock:
            # Инициализируем message_ids, если отсутствует
            if not context.user_data.get('message_ids'):
                context.user_data['message_ids'] = []

            # Добавляем ID сообщения в список
            context.user_data['message_ids'].append(message_id)

            # Ограничиваем количество сохраненных ID до 50 для предотвращения утечек памяти
            if len(context.user_data['message_ids']) > 50:
                context.user_data['message_ids'] = context.user_data['message_ids'][-50:]

    def save_active_message_id(self, update, context, message_id):
        """
        Сохраняет ID активного сообщения с кэшированием.

        Args:
            update (telegram.Update): Объект обновления Telegram
            context (telegram.ext.CallbackContext): Контекст разговора
            message_id (int): ID активного сообщения
        """
        user_id = update.effective_user.id

        with self.message_lock:
            # Сохраняем в контексте пользователя
            context.user_data['active_message_id'] = message_id
            # Также кэшируем для быстрого доступа
            self.active_messages[user_id] = message_id

    def delete_message_safe(self, bot, chat_id, message_id):
        """
        Безопасное удаление сообщения через очередь запросов.
        
        Args:
            bot: Объект бота Telegram
            chat_id: ID чата
            message_id: ID сообщения для удаления
        """
        try:
            # Используем очередь запросов для удаления сообщения
            def delete_func():
                return bot.delete_message(chat_id=chat_id, message_id=message_id)
            
            self.request_queue.enqueue(delete_func)
        except Exception as e:
            # Игнорируем ошибки - часто сообщения уже удалены или недоступны
            pass

    def send_messages_batch(self, context, chat_id, messages, parse_mode='Markdown', 
                         disable_web_page_preview=True, interval=0.5):
        """
        Отправляет несколько сообщений с оптимальными задержками для избежания ограничений API.
        
        Args:
            context (telegram.ext.CallbackContext): Контекст разговора
            chat_id: ID чата для отправки
            messages: Список сообщений для отправки
            parse_mode: Режим форматирования (Markdown, HTML и т.д.)
            disable_web_page_preview: Отключить предпросмотр ссылок
            interval: Интервал между сообщениями в секундах
            
        Returns:
            list: Список ID отправленных сообщений
        """
        sent_message_ids = []
        
        for i, message in enumerate(messages):
            # Контроль размера сообщения
            if len(message) > 4000:
                # Разбиваем длинное сообщение на части по 4000 символов
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    # Очередь запросов обеспечит паузы между отправками
                    def send_func():
                        return context.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            parse_mode=parse_mode,
                            disable_web_page_preview=disable_web_page_preview
                        )
                    
                    # Используем очередь запросов для отправки сообщения
                    sent_message = self.request_queue.enqueue(send_func)
                    if sent_message:
                        sent_message_ids.append(sent_message.message_id)
            else:
                # Отправляем обычное сообщение
                def send_func():
                    return context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
                
                # Используем очередь запросов для отправки сообщения
                sent_message = self.request_queue.enqueue(send_func)
                if sent_message:
                    sent_message_ids.append(sent_message.message_id)
        
        return sent_message_ids

    def clean_chat(self, bot, chat_id, user_id=None):
        """
        Полностью переработанная функция для удаления сообщений чата.
        
        Args:
            bot: Объект бота Telegram
            chat_id: ID чата для очистки
            user_id: ID пользователя (опционально)
            
        Returns:
            bool: Успешность выполнения операции
        """
        try:
            # Логирование начала операции
            self.logger.info(f"Начата очистка чата {chat_id} (пользователь {user_id})")
            
            # Отправляем начальное сообщение
            status_message = None
            try:
                status_message = bot.send_message(
                    chat_id=chat_id,
                    text="🧹 Начинаю очистку чата..."
                )
            except Exception as e:
                self.logger.error(f"Ошибка при отправке начального сообщения: {e}")
            
            # Собираем ID сообщений для удаления
            message_ids = []
            
            # 1. Сначала проверяем сохраненные ID в контексте пользователя
            if user_id and hasattr(bot, 'dispatcher'):
                user_data = bot.dispatcher.user_data.get(user_id, {})
                saved_ids = user_data.get('message_ids', [])
                if saved_ids:
                    message_ids.extend(saved_ids)
                    self.logger.info(f"Получено {len(saved_ids)} сохраненных ID сообщений пользователя")
            
            # Обновляем статус
            if status_message:
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message.message_id,
                        text=f"🧹 Подготовка к очистке...\nНайдено {len(message_ids)} сообщений."
                    )
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении статуса: {e}")
            
            # Если нет сохраненных сообщений, пробуем другие методы
            if not message_ids:
                # Получаем последние сообщения напрямую через API
                self.logger.info("Попытка получить последние сообщения через API...")
                try:
                    # Метод 1: Через телеграм метод getUpdates (для ботов с webhooks может не работать)
                    updates = []
                    try:
                        if hasattr(bot, 'get_updates'):
                            updates = bot.get_updates(offset=-1, limit=100, timeout=1)
                    except Exception as e:
                        self.logger.warning(f"Не удалось получить обновления через get_updates: {e}")
                    
                    for update in updates:
                        if update.message and update.message.chat_id == chat_id:
                            message_ids.append(update.message.message_id)
                    
                    self.logger.info(f"Получено {len(message_ids)} сообщений из обновлений")
                except Exception as e:
                    self.logger.warning(f"Ошибка при попытке получить обновления: {e}")
            
            # Если нет сообщений для удаления, информируем пользователя
            if not message_ids:
                if status_message:
                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_message.message_id,
                            text="⚠️ Не найдено сообщений для удаления."
                        )
                    except:
                        pass
                
                # Отправляем уведомление с кнопками
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать еще раз", callback_data="clear_chat_retry")],
                    [InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                bot.send_message(
                    chat_id=chat_id,
                    text="Не удалось найти сообщения для удаления.\n\nВы можете попробовать еще раз или вернуться в главное меню.",
                    reply_markup=reply_markup
                )
                return False
            
            # Группируем сообщения по 100 (максимальный размер для метода deleteMessages)
            message_chunks = [message_ids[i:i+100] for i in range(0, len(message_ids), 100)]
            total_deleted = 0
            
            # Удаляем сообщения пакетами
            for i, chunk in enumerate(message_chunks):
                try:
                    # Обновляем статус
                    progress = int((i / len(message_chunks)) * 100)
                    if status_message:
                        try:
                            bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=status_message.message_id,
                                text=f"🧹 Очистка чата... {progress}%\nУдалено {total_deleted} из {len(message_ids)} сообщений."
                            )
                        except:
                            pass
                    
                    # Попытка удаления пакета сообщений
                    for msg_id in chunk:
                        try:
                            # Пробуем стандартный метод delete_message
                            def delete_single():
                                try:
                                    return bot.delete_message(chat_id=chat_id, message_id=msg_id)
                                except Exception as e:
                                    self.logger.debug(f"Ошибка при удалении сообщения {msg_id}: {e}")
                                    return False
                            
                            result = self.request_queue.enqueue(delete_single)
                            
                            if result:
                                total_deleted += 1
                                # Делаем небольшую паузу после успешного удаления
                                time.sleep(0.05)
                        except Exception as e:
                            self.logger.debug(f"Ошибка при удалении сообщения {msg_id}: {e}")
                except Exception as e:
                    self.logger.warning(f"Ошибка при обработке пакета сообщений: {e}")
            
            # Очищаем сохраненные ID сообщений пользователя
            if user_id and hasattr(bot, 'dispatcher'):
                user_data = bot.dispatcher.user_data.get(user_id, {})
                if 'message_ids' in user_data:
                    user_data['message_ids'] = []
                    self.logger.info(f"Очищены сохраненные ID сообщений пользователя {user_id}")
            
            # Удаляем статусное сообщение
            if status_message:
                try:
                    bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)
                except:
                    pass
            
            # Отправляем итоговое сообщение
            keyboard = [
                [InlineKeyboardButton("🔄 Повторить очистку", callback_data="clear_chat_retry")],
                [InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            result_text = f"✅ Очистка завершена!\nУдалено {total_deleted} из {len(message_ids)} сообщений."
            if total_deleted < len(message_ids):
                result_text += "\n\nНекоторые сообщения не удалось удалить (возможно, они слишком старые или удалены ранее)."
            
            bot.send_message(
                chat_id=chat_id,
                text=result_text,
                reply_markup=reply_markup
            )
            
            self.logger.info(f"Очистка чата {chat_id} завершена. Удалено {total_deleted} из {len(message_ids)} сообщений.")
            return total_deleted > 0
            
        except Exception as e:
            self.logger.error(f"Критическая ошибка при очистке чата {chat_id}: {e}")
            
            # Отправляем сообщение об ошибке
            try:
                keyboard = [
                    [InlineKeyboardButton("🔄 Повторить", callback_data="clear_chat_retry")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Ошибка при очистке чата:\n{str(e)[:100]}\n\nВы можете попробовать еще раз.",
                    reply_markup=reply_markup
                )
            except:
                pass
            
            return False
    
    # Алиас для обратной совместимости
    delete_chat_history = clean_chat

    def __del__(self):
        """Завершаем очередь запросов при удалении объекта"""
        if hasattr(self, 'request_queue'):
            self.request_queue.stop()

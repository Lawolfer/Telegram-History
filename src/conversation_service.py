
import re
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatAction

class ConversationService:
    """Класс для обработки бесед с пользователем об истории России"""

    def __init__(self, api_client, logger, history_map=None):
        self.api_client = api_client
        self.logger = logger
        self.history_map = history_map

    def handle_conversation(self, update, context, message_manager):
        """
        Обрабатывает сообщения пользователя в режиме беседы с улучшенным распознаванием
        исторических тем и оптимизацией производительности.
        
        Улучшенная обработка ошибок для предотвращения проблем с сообщениями.

        Args:
            update (telegram.Update): Объект обновления Telegram
            context (telegram.ext.CallbackContext): Контекст разговора
            message_manager: Менеджер сообщений для управления историей сообщений

        Returns:
            int: Следующее состояние разговора
        """
        # Проверяем наличие обновления и сообщения
        if not update or not update.message:
            self.logger.error("Получен некорректный объект обновления")
            return None
            
        # Обработка специальных состояний (карта, админ) с оптимизацией
        user_data = context.user_data

        # Проверяем, ожидаем ли мы ввод пользовательской темы для карты
        if user_data.get('waiting_for_map_topic', False):
            return self._handle_map_topic(update, context)

        # Проверяем, ожидаем ли мы ввод ID нового администратора
        if user_data.get('waiting_for_admin_id', False):
            # Передаем обработку в админ-панель
            return None  # Это будет обработано в handlers.py

        try:
            # Основная логика обработки обычных сообщений
            user_message = update.message.text
            user_id = update.message.from_user.id
            
            # Отправляем индикатор набора текста и проверяем доступность чата
            try:
                context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            except Exception as chat_error:
                self.logger.warning(f"Не удалось отправить индикатор набора текста: {chat_error}")
                # Продолжаем работу даже если не удалось отправить индикатор
            
            # Сохраняем сообщение пользователя для контекста
            if 'conversation_history' not in user_data:
                user_data['conversation_history'] = []
                
            # Ограничиваем историю до последних 5 сообщений для оптимизации
            user_data['conversation_history'].append(user_message)
            if len(user_data['conversation_history']) > 5:
                user_data['conversation_history'] = user_data['conversation_history'][-5:]

            # Определяем, связано ли сообщение с историей
            is_history_related = self._is_history_related(user_message, user_data)
            
            if is_history_related:
                # Формируем запрос к API с учетом контекста предыдущих сообщений
                response = self._generate_historical_response(user_message, user_data)
            else:
                # Используем стандартный ответ с подсказками
                response = self._get_default_response()

            # Формируем клавиатуру с дополнительными опциями
            keyboard = [
                [InlineKeyboardButton("🗺️ Карта исторических событий", callback_data='history_map')],
                [InlineKeyboardButton("📚 Изучить тему", callback_data='topic')],
                [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
            ]

            # Проверяем, не был ли удален чат
            if not update.effective_chat:
                self.logger.error(f"Чат не доступен для пользователя {user_id}")
                return None
                
            # Безопасная отправка нового сообщения (не редактирование)
            sent_msg = self._send_response_safely(update, response, keyboard)
            
            # Сохраняем ID сообщения для возможности удаления в будущем
            if sent_msg:
                message_manager.save_message_id(update, context, sent_msg.message_id)
            else:
                self.logger.warning(f"Не удалось отправить ответное сообщение пользователю {user_id}")
                
        except telegram.error.BadRequest as e:
            # Более конкретная обработка ошибки "Message to edit not found"
            if "Message to edit not found" in str(e):
                self.logger.error(f"Ошибка 'Message to edit not found': {e}")
                try:
                    # Отправляем новое сообщение вместо редактирования
                    error_msg = update.message.reply_text(
                        "Не удалось обработать ваш запрос из-за технической ошибки. Пожалуйста, задайте вопрос снова.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]])
                    )
                    message_manager.save_message_id(update, context, error_msg.message_id)
                except Exception as reply_error:
                    self.logger.error(f"Не удалось отправить сообщение об ошибке: {reply_error}")
            else:
                # Общая обработка BadRequest
                self.logger.error(f"Ошибка BadRequest: {e}")
                try:
                    error_msg = update.message.reply_text(
                        "Произошла ошибка при обработке вашего запроса. Попробуйте задать вопрос по-другому.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]])
                    )
                    message_manager.save_message_id(update, context, error_msg.message_id)
                except Exception:
                    pass
                    
        except telegram.error.TelegramError as telegram_error:
            self.logger.error(f"Ошибка Telegram API при обработке беседы: {str(telegram_error)}")
            try:
                # Проверяем, что чат доступен для отправки
                error_msg = update.message.reply_text(
                    "Произошла техническая ошибка при обработке вашего вопроса. Попробуйте вернуться в главное меню и начать беседу заново.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]])
                )
                message_manager.save_message_id(update, context, error_msg.message_id)
            except Exception:
                self.logger.error("Не удалось отправить сообщение об ошибке Telegram API")
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке беседы: {str(e)}")
            try:
                # Отправляем новое сообщение вместо редактирования старого
                error_msg = update.message.reply_text(
                    "Произошла ошибка при обработке вашего вопроса. Попробуйте переформулировать или вернитесь в меню.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]])
                )
                message_manager.save_message_id(update, context, error_msg.message_id)
            except Exception as reply_error:
                self.logger.error(f"Не удалось отправить сообщение об ошибке: {reply_error}")

        # Возвращаем None для продолжения беседы
        # Конкретное значение CONVERSATION будет использовано в handlers.py
        return None  

    def _handle_map_topic(self, update, context):
        """Обрабатывает ввод пользовательской темы для карты"""
        if not self.history_map:
            update.message.reply_text("К сожалению, сервис карт временно недоступен.")
            return None
            
        user_topic = update.message.text
        user_id = update.message.from_user.id

        # Немедленно сбрасываем флаг ожидания
        context.user_data['waiting_for_map_topic'] = False

        self.logger.debug(f"Пользователь {user_id} запросил карту по теме: {user_topic}")

        # Отправляем сообщение о генерации
        status_message = update.message.reply_text(
            f"🔄 Генерация карты по теме «{user_topic}»...",
            parse_mode='HTML'
        )

        try:
            # Запускаем генерацию карты с таймаутом
            import concurrent.futures
            import os
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Запускаем задачу с таймаутом 30 секунд
                future = executor.submit(self.history_map.generate_map_by_topic, user_topic)
                try:
                    map_image_path = future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    map_image_path = None
                    self.logger.error(f"Превышено время ожидания при генерации карты по теме {user_topic}")

            if map_image_path and os.path.exists(map_image_path):
                # Отправляем изображение карты
                with open(map_image_path, 'rb') as img:
                    update.message.reply_photo(
                        photo=img,
                        caption=f"🗺️ Карта по теме «{user_topic}»",
                        parse_mode='HTML'
                    )

                # Удаляем изображение после отправки
                try:
                    os.remove(map_image_path)
                except Exception:
                    pass

                # Предлагаем вернуться к выбору категорий
                keyboard = [
                    [InlineKeyboardButton("🔍 Другая тема", callback_data='map_search_topic'),
                     InlineKeyboardButton("🔙 К категориям", callback_data='history_map')],
                    [InlineKeyboardButton("📋 Главное меню", callback_data='back_to_menu')]
                ]
            else:
                # Если не удалось сгенерировать карту
                keyboard = [
                    [InlineKeyboardButton("🔍 Другая тема", callback_data='map_search_topic'),
                     InlineKeyboardButton("🔙 К категориям", callback_data='history_map')]
                ]
                update.message.reply_text(
                    f"❌ Не удалось найти достаточно событий по теме «{user_topic}».",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            self.logger.error(f"Ошибка при генерации карты: {str(e)}")
            keyboard = [
                [InlineKeyboardButton("🔍 Другая тема", callback_data='map_search_topic'),
                 InlineKeyboardButton("🔙 К категориям", callback_data='history_map')]
            ]
            update.message.reply_text(
                f"❌ Произошла ошибка при генерации карты. Попробуйте другую тему.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # Удаляем сообщение о генерации
        try:
            context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=status_message.message_id
            )
        except:
            pass

        return None  # Значение MAP будет возвращено в handlers.py

    def _is_history_related(self, user_message, user_data):
        """Определяет, связано ли сообщение с историей России"""
        # Расширенный список русскоязычных исторических ключевых слов
        # Разделен на категории для более точного определения исторического контекста
        history_keywords = {
            # Общие исторические термины
            'история', 'исторический', 'историческое', 'исторические', 'исторически',
            'прошлое', 'эпоха', 'период', 'эра', 'век', 'столетие', 'летопись', 'хроника',
            
            # Государственное устройство России
            'россия', 'российская', 'российской', 'российского', 'российскую', 'русь', 
            'киевская', 'московская', 'новгородская', 'владимирская', 'империя', 'ссср', 
            'советский', 'советская', 'советское', 'федерация', 'рсфср', 'российской федерации',
            
            # Правители и политические деятели
            'царь', 'царица', 'княгиня', 'князь', 'император', 'императрица', 'правитель',
            'государь', 'монарх', 'генсек', 'генеральный секретарь', 'президент', 'премьер',
            'династия', 'престол', 'корона', 'трон', 'правление', 'царствование',
            
            # Конкретные исторические личности
            'рюрик', 'олег', 'игорь', 'ольга', 'святослав', 'владимир', 'ярослав', 
            'иван', 'грозный', 'петр', 'екатерина', 'александр', 'николай', 'павел',
            'ленин', 'сталин', 'хрущев', 'брежнев', 'горбачев', 'ельцин', 'путин',
            'романов', 'романовы', 'рюриковичи', 'годунов', 'шуйский',
            
            # Исторические события и процессы
            'война', 'революция', 'восстание', 'бунт', 'переворот', 'реформа', 'перестройка',
            'крепостное', 'крепостничество', 'раскол', 'смута', 'опричнина', 'оттепель', 'застой',
            'коллективизация', 'индустриализация', 'приватизация', 'распад', 'образование',
            
            # Конкретные войны и конфликты
            'отечественная', 'крымская', 'кавказская', 'первая мировая', 'вторая мировая', 
            'гражданская', 'великая отечественная', 'афганская', 'чеченская', 'холодная',
            
            # Географические названия
            'москва', 'петербург', 'ленинград', 'киев', 'новгород', 'псков', 'владимир', 
            'суздаль', 'казань', 'крым', 'сибирь', 'поволжье', 'кавказ', 'урал', 
            'кремль', 'красная площадь', 'зимний дворец',
            
            # Социальные и экономические явления
            'крестьяне', 'дворяне', 'бояре', 'казаки', 'купцы', 'духовенство', 'интеллигенция',
            'помещики', 'крепостные', 'пролетариат', 'буржуазия', 'номенклатура', 'партия',
            'коллективизация', 'индустриализация', 'пятилетка', 'нэп', 'приватизация',
            
            # Сигнальные слова вопросов и запросов
            'когда', 'почему', 'как', 'где', 'какой', 'какие', 'какая', 'кто', 'чем',
            'что случилось', 'что произошло', 'расскажи', 'объясни', 'опиши'
        }

        # Проверка на слова-запросы исторической информации
        history_question_markers = {
            'расскажи', 'объясни', 'опиши', 'поведай', 'поясни',
            'что такое', 'кто такой', 'кто такая', 'когда был', 'когда была',
            'какие были', 'в каком году', 'при каком', 'какое значение'
        }

        # Нормализуем сообщение для анализа
        message_lower = user_message.lower()
        words = set(message_lower.split())
        
        # Проверяем наличие исторических ключевых слов
        is_history_related = bool(words.intersection(history_keywords))
        
        # Если прямых ключевых слов нет, проверяем фразы
        if not is_history_related:
            for marker in history_question_markers:
                if marker in message_lower:
                    is_history_related = True
                    break
        
        # Проверка на наличие вопросительных знаков
        has_question_mark = '?' in user_message
        
        # Анализ предыдущих сообщений для создания контекста
        previous_messages = user_data.get('conversation_history', [])[:-1]  # Все сообщения кроме текущего
        previous_context = " ".join(previous_messages[-2:]) if previous_messages else ""
        
        # Улучшенное определение - сообщение связано с историей, если:
        # 1. Есть ключевые исторические слова
        # 2. Есть вопросительный знак и некоторые базовые слова
        # 3. Предыдущий контекст был историческим и это продолжение разговора
        
        if is_history_related or \
           (has_question_mark and any(word in message_lower for word in ['кто', 'что', 'когда', 'где', 'почему', 'как'])) or \
           (previous_context and any(kw in previous_context.lower() for kw in ['россия', 'история', 'царь', 'война'])):
            return True
            
        return False

    def _generate_historical_response(self, user_message, user_data):
        """Генерирует ответ на исторический вопрос"""
        # Формируем запрос к API с учетом контекста предыдущих сообщений
        previous_messages = user_data.get('conversation_history', [])[:-1]  # Все сообщения кроме текущего
        
        if previous_messages:
            context_prompt = f"Контекст предыдущих сообщений: {' | '.join(previous_messages[-2:])}\n\n"
        else:
            context_prompt = ""
        
        # Создаем детализированный промпт с инструкциями
        prompt = f"""{context_prompt}Ответь на вопрос по истории России: "{user_message}"
        
        Инструкции:
        1. Отвечай кратко и информативно, сосредоточься на исторических фактах.
        2. Упоминай даты и ключевые личности, где уместно.
        3. Если вопрос неясен, интерпретируй его в историческом контексте России.
        4. Максимум 300 слов.
        5. Если вопрос не связан с историей России, вежливо перенаправь на историческую тематику.
        """
        
        # Используем оптимальные параметры для улучшения качества ответа
        response = self.api_client.ask_grok(prompt, max_tokens=800, temp=0.3)
        
        # Постобработка ответа для улучшения читаемости
        response = self._enhance_historical_response(response)
        
        return response

    def _get_default_response(self):
        """Возвращает стандартный ответ с подсказками по тематике"""
        return (
            "Я специализируюсь на истории России и могу ответить на вопросы по следующим темам:\n\n"
            "• Исторические периоды (Киевская Русь, Московское царство, Российская империя, СССР и т.д.)\n"
            "• Правители и исторические личности\n"
            "• Войны и конфликты\n"
            "• Культура и искусство\n"
            "• Реформы и политические изменения\n\n"
            "Пожалуйста, задайте вопрос, связанный с историей России, например:\n"
            "\"Когда произошла Октябрьская революция?\" или \"Расскажи о реформах Петра I\""
        )

    def _send_response_safely(self, update, response, keyboard):
        """
        Безопасно отправляет ответ пользователю с обработкой длинных сообщений 
        и улучшенной обработкой ошибок, избегая редактирования сообщений
        """
        if not update or not update.message:
            self.logger.error("Невозможно отправить сообщение: отсутствует объект update или message")
            return None
            
        try:
            # Проверяем и очищаем ответ, если он пустой или некорректный
            if not response or not isinstance(response, str):
                response = "Извините, не удалось получить ответ на ваш вопрос. Попробуйте задать другой вопрос."
                
            # Если ответ слишком длинный, разбиваем на части (с более строгим лимитом)
            if len(response) > 3000:
                parts = [response[i:i+3000] for i in range(0, len(response), 3000)]
                
                # Отправляем первую часть без клавиатуры
                try:
                    # Используем только reply_text вместо edit_message_text
                    update.message.reply_text(parts[0], parse_mode=None)
                except telegram.error.BadRequest as e:
                    self.logger.error(f"Ошибка при отправке первой части ответа: {e}")
                    # Пробуем отправить более короткую версию
                    try:
                        update.message.reply_text(parts[0][:1000] + "...", parse_mode=None)
                    except Exception as inner_e:
                        self.logger.error(f"Не удалось отправить сокращенную часть ответа: {inner_e}")
                
                # Отправляем средние части, если есть, с обработкой ошибок
                for i, part in enumerate(parts[1:-1], 1):
                    try:
                        update.message.reply_text(part, parse_mode=None)
                    except telegram.error.BadRequest as e:
                        self.logger.warning(f"Не удалось отправить часть {i+1} ответа: {e}")
                        # Пропускаем проблемную часть и продолжаем
                        continue
                    except Exception as e:
                        self.logger.error(f"Неожиданная ошибка при отправке части {i+1}: {e}")
                        continue
                
                # Последнюю часть отправляем с клавиатурой
                try:
                    sent_msg = update.message.reply_text(
                        parts[-1] + "\n\n" + "Вы можете задать ещё вопрос или выбрать другое действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=None
                    )
                    return sent_msg
                except telegram.error.BadRequest as e:
                    self.logger.error(f"Ошибка при отправке последней части ответа: {e}")
                    # Отправляем финальное сообщение без содержимого, только с кнопками
                    try:
                        sent_msg = update.message.reply_text(
                            "Продолжение ответа не удалось отправить. Вы можете задать ещё вопрос или выбрать другое действие:",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=None
                        )
                        return sent_msg
                    except Exception as inner_e:
                        self.logger.error(f"Ошибка при отправке финального сообщения: {inner_e}")
                        return None
            else:
                # Отправляем весь ответ с клавиатурой
                try:
                    # Всегда используем новое сообщение вместо редактирования
                    sent_msg = update.message.reply_text(
                        response + "\n\n" + "Вы можете задать ещё вопрос или выбрать другое действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=None
                    )
                    return sent_msg
                except telegram.error.BadRequest as e:
                    self.logger.error(f"Ошибка при отправке ответа: {e}")
                    # Пробуем отправить сокращенный ответ
                    try:
                        short_response = response[:1000] + "... (ответ сокращен из-за технических ограничений)"
                        sent_msg = update.message.reply_text(
                            short_response + "\n\n" + "Вы можете задать ещё вопрос или выбрать другое действие:",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=None
                        )
                        return sent_msg
                    except Exception as inner_e:
                        self.logger.error(f"Ошибка при отправке сокращенного ответа: {inner_e}")
                        # Если и это не удалось, отправляем только кнопки
                        try:
                            sent_msg = update.message.reply_text(
                                "Не удалось отформатировать ответ. Выберите действие:",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode=None
                            )
                            return sent_msg
                        except Exception as btn_e:
                            self.logger.error(f"Ошибка при отправке кнопок: {btn_e}")
                            return None
                
        except telegram.error.BadRequest as e:
            self.logger.error(f"Ошибка запроса при отправке ответа: {e}")
            # В случае проблем отправляем только кнопки без текста
            try:
                sent_msg = update.message.reply_text(
                    "Извините, произошла ошибка при отправке ответа. Выберите действие:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]]),
                    parse_mode=None
                )
                return sent_msg
            except Exception as menu_e:
                self.logger.error(f"Не удалось отправить кнопку меню: {menu_e}")
                return None
        
        except telegram.error.TelegramError as e:
            self.logger.error(f"Ошибка Telegram API при отправке ответа: {e}")
            # Пробуем отправить минимальное сообщение с кнопкой возврата в меню
            try:
                sent_msg = update.message.reply_text(
                    "Произошла ошибка. Вернитесь в главное меню.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]]),
                    parse_mode=None
                )
                return sent_msg
            except:
                return None
        
        except Exception as e:
            self.logger.error(f"Неизвестная ошибка при отправке ответа: {e}")
            try:
                # Последняя попытка отправить простое сообщение
                sent_msg = update.message.reply_text(
                    "Произошла ошибка. Попробуйте снова или вернитесь в меню.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back_to_menu')]]),
                    parse_mode=None
                )
                return sent_msg
            except:
                return None

    def _enhance_historical_response(self, response):
        """
        Улучшает форматирование исторического ответа для лучшей читаемости.
        
        Args:
            response (str): Исходный ответ от API
            
        Returns:
            str: Отформатированный ответ
        """
        if not response:
            return ""
            
        # Разбиваем длинные абзацы на более короткие для лучшей читаемости
        paragraphs = response.split('\n\n')
        formatted_paragraphs = []
        
        for paragraph in paragraphs:
            # Если абзац слишком длинный, разбиваем его на предложения
            if len(paragraph) > 300:
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                
                # Группируем по 2-3 предложения в абзац
                for i in range(0, len(sentences), 3):
                    end_idx = min(i + 3, len(sentences))
                    formatted_paragraphs.append(' '.join(sentences[i:end_idx]))
            else:
                formatted_paragraphs.append(paragraph)
                
        # Соединяем абзацы обратно с двойным переносом строки
        formatted_text = '\n\n'.join(formatted_paragraphs)
        
        # Проверяем наличие списков и улучшаем их форматирование
        if ':' in formatted_text and ('\n-' in formatted_text or '\n•' in formatted_text):
            # Уже есть списки, сохраняем их форматирование
            pass
        elif ':' in formatted_text and (',' in formatted_text or ';' in formatted_text):
            # Конвертируем перечисления в списки для лучшей читаемости
            lines = formatted_text.split('\n')
            formatted_lines = []
            
            for line in lines:
                if ':' in line and (',' in line.split(':', 1)[1] or ';' in line.split(':', 1)[1]):
                    intro, items_text = line.split(':', 1)
                    items = re.split(r'[,;]\s+', items_text.strip())
                    
                    formatted_lines.append(f"{intro}:")
                    for item in items:
                        if item.strip():
                            formatted_lines.append(f"• {item.strip()}")
                    formatted_lines.append("")  # Пустая строка после списка
                else:
                    formatted_lines.append(line)
                    
            formatted_text = '\n'.join(formatted_lines)
        
        return formatted_text

    def _normalize_russian_input(self, text):
        """
        Нормализует русскоязычный пользовательский ввод для лучшего распознавания команд и тем.
        Обрабатывает опечатки, разные регистры, и формы слов.
        
        Args:
            text (str): Исходный текст
            
        Returns:
            str: Нормализованный текст
        """
        if not text:
            return ""
            
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Словарь распространенных опечаток и альтернативных написаний
        typo_corrections = {
            'истори': 'история',
            'росии': 'россии',
            'руский': 'русский',
            'путен': 'путин',
            'сталин': 'сталин',
            'ленен': 'ленин',
            'ссср': 'ссср',
            'петр': 'петр',
            'екатерин': 'екатерина',
            'революци': 'революция',
            'война': 'война',
            'красн': 'красный',
            'совецк': 'советский',
            'цар': 'царь',
            'импер': 'император'
        }
        
        # Применяем коррекции для основы слова
        words = text.split()
        corrected_words = []
        
        for word in words:
            # Проверяем каждое слово на наличие опечаток
            corrected = word
            for typo, correction in typo_corrections.items():
                if word.startswith(typo):
                    corrected = correction + word[len(typo):]
                    break
                    
            corrected_words.append(corrected)
            
        # Собираем обратно в строку
        normalized_text = ' '.join(corrected_words)
        
        # Заменяем часто смешиваемые символы (латинские/кириллические)
        char_replacements = {
            'a': 'а',  # латинская -> кириллическая
            'e': 'е',
            'o': 'о',
            'p': 'р',
            'c': 'с',
            'x': 'х',
            'b': 'в',
            'h': 'н',
            'y': 'у'
        }
        
        for lat, cyr in char_replacements.items():
            normalized_text = normalized_text.replace(lat, cyr)
            
        return normalized_text

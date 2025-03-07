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
        Обрабатывает сообщения пользователя в режиме беседы без использования
        редактирования сообщений для предотвращения ошибок.

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

        # Получаем данные пользователя для контекста
        user_data = context.user_data
        user_id = update.message.from_user.id
        user_message = update.message.text

        # Обработка специальных состояний
        # Проверяем, ожидаем ли мы ввод пользовательской темы для карты
        if user_data.get('waiting_for_map_topic', False):
            return self._handle_map_topic(update, context)

        # Проверяем, ожидаем ли мы ввод ID нового администратора
        if user_data.get('waiting_for_admin_id', False):
            # Передаем обработку в админ-панель
            return None  # Это будет обработано в handlers.py

        try:
            # Показываем пользователю, что бот печатает
            try:
                context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            except Exception as chat_error:
                self.logger.warning(f"Не удалось отправить индикатор набора текста: {chat_error}")

            # Сохраняем историю сообщений пользователя для контекста
            if 'conversation_history' not in user_data:
                user_data['conversation_history'] = []

            # Ограничиваем историю до последних 5 сообщений для оптимизации
            user_data['conversation_history'].append(user_message)
            if len(user_data['conversation_history']) > 5:
                user_data['conversation_history'] = user_data['conversation_history'][-5:]

            # Определяем, связано ли сообщение с историей
            is_history_related = self._is_history_related(user_message, user_data)

            # Генерируем ответ в зависимости от типа сообщения
            if is_history_related:
                response = self._generate_historical_response(user_message, user_data)
            else:
                response = self._get_default_response()

            # Клавиатура с дополнительными опциями
            keyboard = [
                [InlineKeyboardButton("🗺️ Карта исторических событий", callback_data='history_map')],
                [InlineKeyboardButton("📚 Изучить тему", callback_data='topic')],
                [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]
            ]

            # Отправляем ответ частями, если он слишком длинный
            sent_messages = self._send_message_in_parts(update, response, keyboard)

            # Сохраняем ID отправленных сообщений для будущей очистки
            for msg_id in sent_messages:
                message_manager.save_message_id(update, context, msg_id)

            return None  # Остаемся в режиме беседы

        except Exception as e:
            self.logger.error(f"Ошибка при обработке беседы: {str(e)}")
            try:
                # Отправляем сообщение об ошибке
                error_msg = update.message.reply_text(
                    "Произошла ошибка при обработке вашего вопроса. Попробуйте задать другой вопрос или вернуться в меню.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_menu')]])
                )
                message_manager.save_message_id(update, context, error_msg.message_id)
            except Exception as reply_error:
                self.logger.error(f"Не удалось отправить сообщение об ошибке: {reply_error}")

            return None

    def _send_message_in_parts(self, update, text, keyboard=None):
        """
        Разбивает длинное сообщение на части и отправляет их последовательно.

        Args:
            update: Объект обновления Telegram
            text: Текст для отправки
            keyboard: Клавиатура для добавления к последнему сообщению

        Returns:
            list: Список ID отправленных сообщений
        """
        if not text:
            text = "Извините, не удалось получить ответ на ваш вопрос."

        sent_message_ids = []
        max_length = 3000  # Максимальная длина одного сообщения

        # Если текст короче максимальной длины, отправляем его целиком
        if len(text) <= max_length:
            try:
                # Формируем текст с подсказкой
                if keyboard:
                    full_text = f"{text}\n\nВы можете задать ещё вопрос или выбрать другое действие:"
                else:
                    full_text = text

                # Отправляем сообщение
                sent_msg = update.message.reply_text(
                    full_text,
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                    parse_mode=None
                )
                sent_message_ids.append(sent_msg.message_id)

            except Exception as e:
                self.logger.error(f"Ошибка при отправке сообщения: {e}")
                try:
                    # Пробуем отправить без форматирования и с меньшим текстом
                    sent_msg = update.message.reply_text(
                        text[:1000] + "... (сообщение сокращено)",
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )
                    sent_message_ids.append(sent_msg.message_id)
                except Exception as inner_e:
                    self.logger.error(f"Не удалось отправить сокращенное сообщение: {inner_e}")
        else:
            # Разбиваем текст на части по абзацам
            paragraphs = text.split('\n\n')
            current_part = ""
            parts = []

            for paragraph in paragraphs:
                # Если добавление этого абзаца превысит лимит
                if len(current_part) + len(paragraph) + 2 > max_length:
                    parts.append(current_part)
                    current_part = paragraph
                else:
                    if current_part:
                        current_part += '\n\n' + paragraph
                    else:
                        current_part = paragraph

            # Добавляем последнюю часть
            if current_part:
                parts.append(current_part)

            # Если разбиение по абзацам не помогло (очень длинные абзацы)
            if not parts or (len(parts) == 1 and len(parts[0]) > max_length):
                # Разбиваем принудительно по максимальной длине
                parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]

            # Отправляем части последовательно
            for i, part in enumerate(parts):
                try:
                    # К последней части добавляем клавиатуру
                    if i == len(parts) - 1 and keyboard:
                        sent_msg = update.message.reply_text(
                            part + "\n\nВы можете задать ещё вопрос или выбрать другое действие:",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=None
                        )
                    else:
                        sent_msg = update.message.reply_text(part, parse_mode=None)

                    sent_message_ids.append(sent_msg.message_id)

                except Exception as e:
                    self.logger.error(f"Ошибка при отправке части {i+1}: {e}")
                    # Продолжаем с следующей частью
                    continue

            # Если не удалось отправить ни одной части или последнюю часть с клавиатурой
            if not sent_message_ids or (keyboard and len(parts) > 1 and len(sent_message_ids) < len(parts)):
                try:
                    # Отправляем кнопки отдельным сообщением
                    sent_msg = update.message.reply_text(
                        "Вы можете задать ещё вопрос или выбрать другое действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=None
                    )
                    sent_message_ids.append(sent_msg.message_id)
                except Exception as e:
                    self.logger.error(f"Не удалось отправить кнопки: {e}")

        return sent_message_ids

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
        # Обратите внимание: метод ask_grok теперь не использует max_tokens и temp
        try:
            response = self.api_client.ask_grok(prompt, use_cache=True)
        except Exception as e:
            self.logger.error(f"Ошибка при запросе к API: {e}")
            response = "Извините, не удалось получить ответ на ваш вопрос. Попробуйте переформулировать вопрос или задать другой."

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
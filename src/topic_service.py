import re
import random
import textwrap

class TopicService:
    """Класс для работы с темами по истории России"""

    def __init__(self, api_client, logger):
        """
        Инициализация сервиса тем

        Args:
            api_client: Клиент API для получения данных
            logger: Логгер для записи действий
        """
        self.api_client = api_client
        self.logger = logger

        # Список стандартных глав для каждой темы
        self.standard_chapters = [
            "Истоки и предпосылки",
            "Ключевые события", 
            "Исторические личности",
            "Международный контекст",
            "Историческое значение"
        ]

        # Эмодзи для глав
        self.chapter_emoji = {
            "Истоки и предпосылки": "🔍",
            "Ключевые события": "📅",
            "Исторические личности": "👥",
            "Международный контекст": "🌍",
            "Историческое значение": "⚖️"
        }

        # Максимальный размер сообщения в Telegram (символов)
        self.max_message_size = 4000

    def generate_topics_list(self, use_cache=True):
        """
        Генерирует список тем по истории России

        Args:
            use_cache (bool): Использовать ли кэш

        Returns:
            list: Список тем
        """
        prompt = "Составь список из 30 ключевых тем по истории России, которые могут быть интересны для изучения. Каждая тема должна быть емкой и конкретной (не более 6-7 слов). Перечисли их в виде нумерованного списка."
        topics_text = self.api_client.ask_grok(prompt, use_cache=use_cache)

        # Парсим и возвращаем темы
        return self.parse_topics(topics_text)

    def generate_new_topics_list(self):
        """
        Генерирует новый список тем с разнообразным содержанием

        Returns:
            list: Новый список тем
        """
        # Добавляем случайный параметр для получения разных тем
        random_seed = random.randint(1, 1000)
        prompt = f"Составь список из 30 новых и оригинальных тем по истории России, которые могут быть интересны для изучения. Сосредоточься на темах {random_seed}. Выбери темы, отличные от стандартных и ранее предложенных. Каждая тема должна быть емкой и конкретной (не более 6-7 слов). Перечисли их в виде нумерованного списка."

        # Отключаем кэширование для получения действительно новых тем
        topics_text = self.api_client.ask_grok(prompt, use_cache=False)

        # Парсим и возвращаем темы
        return self.parse_topics(topics_text)

    def parse_topics(self, topics_text):
        """
        Парсит темы из текстового ответа API

        Args:
            topics_text (str): Текстовый ответ от API

        Returns:
            list: Список тем
        """
        topics = []

        # Разбиваем текст на строки и ищем нумерованные пункты
        for line in topics_text.splitlines():
            # Ищем строки вида "1. Тема" или "1) Тема"
            match = re.match(r'^\s*(\d+)[\.\)]\s+(.*?)$', line)
            if match:
                number, topic = match.groups()
                # Добавляем тему с номером для сохранения порядка
                topics.append(f"{number}. {topic.strip()}")

        # Если ничего не нашли, пробуем другие форматы
        if not topics:
            for line in topics_text.splitlines():
                # Ищем строки, которые могут быть темами без нумерации
                if line.strip() and not line.startswith('#') and not line.startswith('**'):
                    topics.append(line.strip())

        # Очищаем список от возможных дубликатов
        filtered_topics = []
        seen_topics = set()

        for topic in topics:
            # Извлекаем текст темы без номера
            text = topic.split('. ', 1)[1] if '. ' in topic else topic
            text_lower = text.lower()

            # Добавляем только если такой темы еще не было
            if text_lower not in seen_topics:
                filtered_topics.append(topic)
                seen_topics.add(text_lower)

        return filtered_topics

    def get_cached_topic_info(self, topic, update_callback=None, text_cache_service=None):
        """
        Получает информацию по теме из кэша или генерирует новую

        Args:
            topic (str): Тема для получения информации
            update_callback (function): Функция обратного вызова для обновления статуса
            text_cache_service (TextCacheService): Сервис кэширования текстов

        Returns:
            list: Список сообщений с информацией по теме
        """
        if not topic:
            return ["Пожалуйста, укажите тему для получения информации."]
            
        # Проверяем кэш, если сервис кэширования предоставлен
        if text_cache_service:
            cache_key_type = "topic_info"
            cached_content = text_cache_service.get_text(topic, cache_key_type)
            
            if cached_content:
                # Нашли в кэше - десериализуем и возвращаем
                if update_callback:
                    update_callback(f"📝 Загружаю информацию по теме: *{topic}* из кэша...")
                
                self.logger.info(f"Информация по теме '{topic}' загружена из кэша")
                
                try:
                    # Предполагаем, что в кэше хранится JSON-строка с сообщениями
                    import json
                    return json.loads(cached_content)
                except Exception as e:
                    self.logger.error(f"Ошибка при десериализации кэшированной темы '{topic}': {e}")
                    # В случае ошибки - сгенерируем заново
            
            if update_callback:
                update_callback(f"🔄 Не найдено в кэше. Генерирую информацию по теме: *{topic}*...")
        
        # Генерируем новую информацию по теме
        messages = self.get_topic_info(topic, update_callback)
        
        # Сохраняем в кэш, если сервис кэширования предоставлен и данные успешно получены
        if text_cache_service and messages and len(messages) > 1 and not messages[0].startswith("⚠️"):
            try:
                # Сериализуем сообщения для хранения в кэше
                import json
                serialized_messages = json.dumps(messages, ensure_ascii=False)
                text_cache_service.save_text(topic, "topic_info", serialized_messages)
                self.logger.info(f"Информация по теме '{topic}' сохранена в кэш")
            except Exception as e:
                self.logger.error(f"Ошибка при сохранении темы '{topic}' в кэш: {e}")
        
        return messages

    def get_topic_info(self, topic, update_callback=None):
        """
        Получает подробную информацию по теме, разбитую на главы

        Args:
            topic (str): Тема для получения информации
            update_callback (function): Функция обратного вызова для обновления статуса

        Returns:
            list: Список сообщений с информацией по теме (по одному на каждую главу)
        """
        try:
            # Функция для очистки текста от специальных символов для безопасной обработки
            def sanitize_markdown(text):
                if not text:
                    return ""
                # Экранируем специальные символы Markdown
                chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                for char in chars_to_escape:
                    text = text.replace(char, '\\' + char)
                return text

            # Очищаем пользовательский ввод
            safe_topic = sanitize_markdown(topic)
            chapters = self.standard_chapters

            if update_callback:
                update_callback(f"🔍 Собираю информацию по теме: *{topic}*...")

            # Получаем общий контекст для темы для более точного последующего запроса
            context_prompt = f"""Определи детальные характеристики и рамки темы "{safe_topic}" из истории России.
            Укажи:
            1. Точные хронологические рамки (годы, века, периоды)
            2. Географический охват (территории, регионы)
            3. Ключевых исторических деятелей, связанных с темой
            4. Основные события в хронологическом порядке
            5. Главные документы/акты/законы, если применимо

            Ответ должен быть конкретным, точным и информативным.
            """

            # Получаем общий контекст для темы без использования кэша
            self.logger.info(f"Запрашиваю общий контекст для темы '{topic}'")
            topic_context = self.api_client.ask_grok(context_prompt, use_cache=False)

            if update_callback:
                update_callback(f"📚 Формирую главы для темы: *{topic}*...")

            # Получаем информацию для каждой главы отдельно
            chapters_content = {}

            for i, chapter in enumerate(chapters):
                if update_callback:
                    update_callback(f"📝 Работаю над главой {i+1}: *{chapter}*...")

                # Формируем специализированный запрос для каждой главы
                chapter_prompt = self._get_chapter_prompt(chapter, safe_topic)

                # Добавляем контекст темы к запросу
                full_prompt = f"""Контекст темы: {topic_context}

ВАЖНО: Ты высококвалифицированный историк, специализирующийся на истории России. Твоя задача - предоставить глубокий, детальный и достоверный анализ темы "{safe_topic}" для образовательного телеграм-бота.

{chapter_prompt}

ТРЕБОВАНИЯ К КАЧЕСТВУ ОТВЕТА:
1. Абсолютная историческая точность и достоверность
2. Максимальная конкретика (точные даты, имена, цифры, места)
3. Академический, но доступный стиль изложения
4. Логическая структурированность материала
5. Отсутствие общих фраз и "воды"
6. Недопустимость анахронизмов и исторических ошибок
7. Соответствие современным научным представлениям
8. Объективность и беспристрастность изложения

Начинай сразу с информативного содержания, без вводных фраз и заголовков.
Текст должен быть готов к непосредственному использованию в качестве учебного материала.
"""

                # Получаем ответ без кэширования 
                # Попытаемся до 3-х раз получить качественный ответ
                for attempt in range(3):
                    self.logger.info(f"Запрос информации для главы '{chapter}', попытка {attempt+1}")
                    chapter_content = self.api_client.ask_grok(full_prompt, use_cache=False)

                    # Проверяем качество ответа - он должен быть достаточно информативным
                    if len(chapter_content) >= 1500:
                        break  # Достаточный объем

                    # Если ответ короткий, повторяем запрос с усилением требований
                    if update_callback:
                        update_callback(f"⚠️ Получена неполная информация для главы {i+1}. Пробую снова...")

                    # Усиливаем запрос для следующей попытки
                    full_prompt += f"\n\nПОЛУЧЕННЫЙ ОТВЕТ НЕДОСТАТОЧЕН! Предыдущий ответ был слишком коротким ({len(chapter_content)} символов). Требуется МИНИМУМ 1500 символов с подробной, конкретной и точной информацией. Пожалуйста, предоставь гораздо более детальный и информативный ответ."

                chapters_content[chapter] = chapter_content
                self.logger.info(f"Получена информация для главы '{chapter}' по теме '{topic}': {len(chapter_content)} символов")

            if update_callback:
                update_callback(f"✏️ Форматирую материал по теме: *{topic}*...")

            # Формируем сообщения на основе собранной информации по главам
            messages = self._format_topic_messages(topic, chapters_content)

            # Если не удалось сформировать сообщения, возвращаем ошибку
            if not messages:
                return [f"⚠️ Не удалось получить информацию по теме: {topic}. Пожалуйста, попробуйте другую тему."]

            return messages

        except Exception as e:
            self.logger.error(f"Ошибка при получении информации по теме {topic}: {e}")
            return [f"⚠️ Не удалось получить информацию по теме: {topic}. Ошибка: {str(e)}"]

    def _get_chapter_prompt(self, chapter, topic):
        """
        Возвращает промпт для получения информации по конкретной главе

        Args:
            chapter (str): Название главы
            topic (str): Название темы

        Returns:
            str: Промпт для запроса информации
        """
        # Словарь с промптами для разных глав
        chapter_prompts = {
            "Истоки и предпосылки": f"""Предоставь глубокий и подробный анализ истоков и предпосылок темы "{topic}" из истории России.

            Обязательно рассмотри:
            1. Исторический контекст и особенности эпохи, в которой происходили события (с конкретными датами)
            2. Политическая ситуация в России и мире накануне описываемых событий
            3. Экономические факторы и условия, повлиявшие на развитие темы
            4. Социальная структура общества и взаимоотношения различных классов/сословий
            5. Культурные и идеологические предпосылки
            6. Ключевые события-предшественники с точными датами
            7. Причинно-следственные связи между предшествующими событиями и рассматриваемой темой

            Текст должен включать:
            • Точные даты, годы, периоды
            • Имена реальных исторических личностей с их должностями/титулами
            • Названия географических объектов, где происходили события
            • Статистические данные (если применимо)

            Текст должен быть структурированным, информативным и строго объективным.
            Используй только проверенные исторические сведения. 
            Объем: 4-5 содержательных абзацев, не повторяйся.
            """,

            "Ключевые события": f"""Предоставь детальную хронологию и анализ ключевых событий темы "{topic}" из истории России.

            Обязательно включи:
            1. Строгую хронологическую последовательность событий с максимально точными датами (день, месяц, год - где это возможно)
            2. Подробное описание каждого ключевого события с указанием места, участников и обстоятельств
            3. Разделение на логические этапы или фазы (если применимо)
            4. Поворотные моменты, критические точки и переломные события
            5. Действия основных участников в каждом важном событии
            6. Промежуточные результаты каждого значимого события
            7. Данные о численности войск, потерях, материальных затратах (для военных событий)
            8. Технические, тактические, стратегические аспекты (если уместно)

            Текст должен быть:
            • Максимально детализированным, с точными цифрами и данными
            • Разделенным на логические части по хронологии или значимости
            • Хорошо структурированным, с четкими причинно-следственными связями

            Объем: не менее 5-6 содержательных абзацев с конкретными фактами.
            Не повторяй информацию из других разделов.
            """,

            "Исторические личности": f"""Представь детальный анализ роли исторических личностей в теме "{topic}" из истории России.

            Для каждой ключевой личности (не менее 5-6) укажи:
            1. Полное имя, годы жизни, занимаемые должности или титулы
            2. Краткие биографические сведения, имеющие отношение к теме
            3. Образование, взгляды, убеждения, влиявшие на принятие решений
            4. Конкретные действия, решения, поступки в контексте рассматриваемых событий
            5. Цели, мотивы, интересы данного исторического деятеля
            6. Отношения с другими историческими личностями в контексте темы
            7. Оценку эффективности действий, влияния на ход событий, исторического значения
            8. Интересные факты, характеризующие личность в контексте темы

            Обязательно включи как первостепенных деятелей, так и менее известных, но значимых персон.
            Для противоборствующих сторон (если применимо) представь ключевых личностей каждой стороны.

            Структурируй текст по персоналиям, четко выделяя информацию о каждом деятеле.
            Объем: 5-6 содержательных абзацев с конкретными и точными фактами.
            Избегай повторения информации из других разделов.
            """,

            "Международный контекст": f"""Разработай всесторонний анализ международного контекста и внешнеполитических аспектов темы "{topic}" из истории России.

            Обязательно охвати:
            1. Детальное описание международной обстановки в рассматриваемый период
            2. Интересы и позиции ключевых иностранных держав относительно России и темы
            3. Изменения в системе международных отношений, произошедшие в результате событий
            4. Конкретные дипломатические переговоры, встречи, соглашения с точными датами
            5. Международные договоры, пакты, альянсы (с подробностями их содержания)
            6. Военные, экономические, политические аспекты взаимодействия России с другими странами
            7. Реакция мировой общественности, печати, политиков на события в России
            8. Влияние международных факторов на внутренние процессы в России

            Для каждой упомянутой страны укажи:
            • Её интересы и цели в отношении России
            • Конкретные действия и решения её правительства
            • Имена ключевых зарубежных государственных деятелей
            • Изменение её позиции в ходе развития событий (если происходило)

            Объем: 5-6 содержательных абзацев с фактическим материалом.
            Текст должен содержать точные даты, названия договоров, имена иностранных деятелей.
            """,

            "Историческое значение": f"""Предоставь глубокий и многоаспектный анализ исторического значения и долгосрочных последствий темы "{topic}" для истории России.

            Рассмотри следующие аспекты:
            1. Непосредственные итоги и результаты событий/процессов с конкретными данными
            2. Политические последствия (изменения в государственном устройстве, законодательстве, политике)
            3. Экономические последствия (изменения в хозяйственной системе, финансах, торговле)
            4. Социальные последствия (изменения в обществе, положении различных слоев населения)
            5. Культурные и идеологические последствия (влияние на культуру, науку, образование)
            6. Военные и геополитические последствия (изменения границ, военной мощи, международного положения)
            7. Влияние на дальнейшие исторические периоды и события с конкретными примерами
            8. Оценки и интерпретации значения темы историками разных эпох и направлений
            9. Отражение темы в исторической памяти, памятниках, мемориалах, исторической политике
            10. Актуальность и значение темы для современной России

            Сопоставь различные точки зрения на значение этой темы, приведи разные оценки историков.
            Проанализируй как краткосрочные, так и долгосрочные последствия, прослеживая их влияние на последующие периоды.

            Текст должен быть аналитическим, с конкретными примерами и фактами.
            Объем: не менее 5-6 содержательных аналитических абзацев.
            """
        }

        # Возвращаем промпт для запрошенной главы или стандартный промпт, если глава не найдена
        return chapter_prompts.get(chapter, f"Предоставь подробную информацию о {chapter.lower()} по теме '{topic}' из истории России. Включи конкретные даты, места, имена исторических личностей и документов. Избегай общих фраз и используй только проверенные исторические факты.")

    def _format_topic_messages(self, topic, chapters_content):
        """
        Форматирует контент темы и разбивает его на отдельные сообщения по главам

        Args:
            topic (str): Название темы
            chapters_content (dict): Словарь с содержимым глав

        Returns:
            list: Список отформатированных сообщений
        """
        messages = []

        # Сначала создаем оглавление с общей информацией о теме
        toc_message = f"📚 *{topic.upper()}*\n\n┏━━━━━━━━━━━━━━━━━━━━━━━━┓"
        toc_message += "\n\n📋 *ОГЛАВЛЕНИЕ:*\n"

        for i, chapter in enumerate(self.standard_chapters, 1):
            emoji = self.chapter_emoji.get(chapter, "•")
            toc_message += f"{emoji} *Глава {i}:* {chapter}\n"

        toc_message += "\n┗━━━━━━━━━━━━━━━━━━━━━━━━┛"

        # Добавляем оглавление как первое сообщение
        messages.append(toc_message)

        # Теперь формируем сообщения для каждой главы
        for i, chapter in enumerate(self.standard_chapters, 1):
            emoji = self.chapter_emoji.get(chapter, "•")
            content = chapters_content.get(chapter, "")

            # Если содержимое главы пустое, добавляем заглушку
            if not content:
                empty_message = f"{emoji} *ГЛАВА {i}: {chapter.upper()}*\n\n"
                empty_message += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
                empty_message += "ℹ️ _Информация по данной главе отсутствует._"

                if i < len(self.standard_chapters):
                    empty_message += f"\n\n•┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈•\n\n➡️ *Далее:* Глава {i+1}: {self.standard_chapters[i]}"
                else:
                    empty_message += f"\n\n•┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈•\n\n📝 *Конец материала*"

                messages.append(empty_message)
                continue

            # Подготавливаем текст главы, форматируя его
            formatted_content = self._format_chapter_content(content)

            # Формируем заголовок главы
            chapter_header = f"{emoji} *ГЛАВА {i}: {chapter.upper()}*\n\n"
            chapter_header += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"

            # Добавляем навигационный футер
            if i < len(self.standard_chapters):
                footer = f"\n\n•┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈•\n\n➡️ *Далее:* Глава {i+1}: {self.standard_chapters[i]}"
            else:
                footer = f"\n\n•┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈•\n\n📝 *Конец материала*"

            # Проверяем, нужно ли разделять сообщение из-за превышения размера
            full_message = chapter_header + formatted_content + footer

            if len(full_message) > self.max_message_size:
                # Разбиваем контент на части
                # Учитываем размер заголовка и футера
                available_size = self.max_message_size - len(chapter_header) - 100

                # Разбиваем контент на абзацы
                paragraphs = formatted_content.split('\n\n')

                # Собираем части сообщения
                current_part = ""
                part_messages = []

                for paragraph in paragraphs:
                    if len(current_part) + len(paragraph) + 4 <= available_size:
                        if current_part:
                            current_part += "\n\n" + paragraph
                        else:
                            current_part = paragraph
                    else:
                        # Добавляем текущую часть в список
                        if current_part:
                            part_messages.append(current_part)
                        current_part = paragraph

                # Добавляем последнюю часть
                if current_part:
                    part_messages.append(current_part)

                # Формируем сообщения с частями главы
                for j, part in enumerate(part_messages, 1):
                    part_prefix = f"{emoji} *ГЛАВА {i}: {chapter.upper()}* (часть {j}/{len(part_messages)})\n\n"
                    part_prefix += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"

                    # Для последней части добавляем футер с навигацией
                    if j == len(part_messages):
                        messages.append(part_prefix + part + footer)
                    else:
                        messages.append(part_prefix + part)
            else:
                # Если сообщение не превышает лимит, отправляем его целиком
                messages.append(full_message)

        return messages

    def _format_chapter_content(self, content):
        """
        Форматирует содержимое главы для лучшей читаемости

        Args:
            content (str): Исходный текст главы

        Returns:
            str: Отформатированный текст главы
        """
        # Разбиваем контент на абзацы
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', content) if p.strip()]

        # Если получился один большой абзац, разбиваем его на более мелкие
        if len(paragraphs) <= 2 and any(len(p) > 400 for p in paragraphs):
            new_paragraphs = []
            for paragraph in paragraphs:
                # Разбиваем длинные абзацы на смысловые блоки по точкам
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)

                # Группируем по 2-3 предложения в один абзац
                for i in range(0, len(sentences), 2):
                    if i+1 < len(sentences):
                        new_paragraphs.append(sentences[i] + " " + sentences[i+1])
                    else:
                        new_paragraphs.append(sentences[i])
            paragraphs = new_paragraphs

        # Форматируем каждый абзац с улучшенной читаемостью
        formatted_paragraphs = []

        for idx, paragraph in enumerate(paragraphs):
            # Убираем лишние переносы строк внутри абзаца
            clean_paragraph = re.sub(r'\n+', ' ', paragraph)

            # Выделяем даты и важные события жирным шрифтом
            clean_paragraph = re.sub(r'(\d{4}(-\d{4})? (год|гг)|\d{1,2}-\d{1,2} век|[XIV]{1,5} в\.)', r'*\1*', clean_paragraph)

            # Выделяем имена исторических личностей
            clean_paragraph = re.sub(r'(царь|император|князь|королева|премьер-министр|президент|военачальник) ([А-Я][а-я]+ [А-Я][а-я]+)', r'\1 *\2*', clean_paragraph)

            # Выделяем ключевые термины
            key_terms = ["реформа", "революция", "война", "договор", "восстание", "манифест", "указ"]
            for term in key_terms:
                clean_paragraph = re.sub(rf'({term}[а-я]*)', r'_\1_', clean_paragraph, flags=re.IGNORECASE)

            # Если есть перечисление через запятые, преобразуем в список
            if len(clean_paragraph) > 300 and ":" in clean_paragraph and ("," in clean_paragraph or ";" in clean_paragraph):
                try:
                    intro, items_text = clean_paragraph.split(":", 1)
                    items = re.split(r'[,;]\s+', items_text)

                    if len(items) >= 3:  # Если есть достаточно элементов для списка
                        bullet_list = [intro + ":"]
                        for item in items:
                            if item.strip():
                                bullet_list.append(f"• {item.strip()}")

                        clean_paragraph = "\n".join(bullet_list)
                except Exception:
                    pass  # Если не удалось разбить на список, оставляем как есть

            formatted_paragraphs.append(clean_paragraph)

        # Соединяем отформатированные абзацы
        return "\n\n".join(formatted_paragraphs)
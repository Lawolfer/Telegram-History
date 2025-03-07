
import re
import random

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
    
    def get_topic_info(self, topic, update_callback=None):
        """
        Получает подробную информацию по теме
        
        Args:
            topic (str): Тема для получения информации
            update_callback (function): Функция обратного вызова для обновления статуса
            
        Returns:
            dict: Информация по теме
        """
        try:
            chapters = [
                "Истоки и предпосылки",
                "Ключевые события",
                "Исторические личности",
                "Международный контекст",
                "Историческое значение"
            ]
            
            # Формируем запрос на получение структурированной информации по теме
            prompt = f"""Предоставь структурированную информацию по теме "{topic}" из истории России.
            Раздели ответ на следующие главы:
            1. {chapters[0]}: предыстория, причины возникновения, контекст эпохи
            2. {chapters[1]}: хронология, основные этапы, ключевые даты
            3. {chapters[2]}: важные исторические фигуры, их роль и вклад
            4. {chapters[3]}: взаимосвязь с мировыми событиями, внешняя политика
            5. {chapters[4]}: последствия, влияние на дальнейшую историю

            Используй только проверенные исторические факты. Придерживайся нейтрального стиля изложения.
            Текст должен быть информативным и хорошо структурированным для образовательных целей.
            """
            
            if update_callback:
                update_callback(f"🔍 Собираю информацию по теме: *{topic}*...")
            
            response = self.api_client.ask_grok(prompt)
            
            if update_callback:
                update_callback(f"✏️ Форматирую материал по теме: *{topic}*...")
            
            # Форматируем результат
            formatted_content = self._format_content_with_chapters(response, chapters, topic)
            
            return {
                "status": "success",
                "content": formatted_content
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении информации по теме {topic}: {e}")
            return {
                "status": "error",
                "content": f"Не удалось получить информацию по теме: {topic}. Ошибка: {str(e)}"
            }
    
    def _format_content_with_chapters(self, content, chapters, topic):
        """
        Форматирует контент с разделением на главы
        
        Args:
            content (str): Исходный контент
            chapters (list): Список названий глав
            topic (str): Название темы
            
        Returns:
            str: Отформатированный контент
        """
        formatted_content = f"# {topic}\n\n"
        
        # Разбиваем контент на главы
        chapter_contents = {}
        current_chapter = None
        
        for line in content.split('\n'):
            # Проверяем, является ли строка заголовком главы
            for i, chapter in enumerate(chapters, 1):
                if chapter in line or f"{i}." in line or f"{i}:" in line:
                    current_chapter = chapter
                    chapter_contents[current_chapter] = []
                    break
            
            # Добавляем строку к текущей главе
            if current_chapter:
                chapter_contents[current_chapter].append(line)
        
        # Форматируем главы в Markdown
        for i, chapter in enumerate(chapters):
            if chapter in chapter_contents:
                chapter_text = '\n'.join(chapter_contents[chapter])
                # Удаляем номер главы из текста, если он есть
                chapter_text = re.sub(r'^\d+[\.\:\)]?\s*', '', chapter_text)
                # Удаляем название главы из текста, если оно есть
                chapter_text = re.sub(re.escape(chapter), '', chapter_text, flags=re.IGNORECASE)
                
                formatted_content += f"## {chapter}\n\n{chapter_text.strip()}\n\n"
            else:
                # Если глава не найдена, используем весь контент
                if i == 0 and not chapter_contents:
                    formatted_content += content
                    break
        
        return formatted_content

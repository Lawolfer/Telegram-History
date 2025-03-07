
import threading
import re
import random
import time

class ContentService:
    """Класс для обработки и получения образовательного контента"""
    
    def __init__(self, api_client, logger):
        self.api_client = api_client
        self.logger = logger
    
    def get_topic_info(self, topic, update_message_func=None):
        """
        Получает информацию о теме из API и форматирует её для отправки с оптимизацией.

        Args:
            topic (str): Тема для изучения
            update_message_func (callable, optional): Функция для обновления сообщенияо загрузке

        Returns:
            list: Список сообщений для отправки
        """
        chapter_titles = [
            "📜 ВВЕДЕНИЕ И ИСТОКИ",
            "⚔️ ОСНОВНЫЕ СОБЫТИЯ И РАЗВИТИЕ",
            "🏛️ КЛЮЧЕВЫЕ ФИГУРЫ И РЕФОРМЫ",
            "🌍 ВНЕШНЯЯ ПОЛИТИКА И ВЛИЯНИЕ",
            "📊 ИТОГИ И ИСТОРИЧЕСКОЕ ЗНАЧЕНИЕ"
        ]

        prompts = [
            f"Расскажи о {topic} в истории России (глава 1). Дай введение и начальную историю, истоки темы. Используй структурированное изложение. Объем - один абзац. Не пиши 'продолжение следует'.",
            f"Расскажи о {topic} в истории России (глава 2). Опиши основные события и развитие. Не делай вступление, продолжай повествование. Объем - один абзац. Не пиши 'продолжение следует'.",
            f"Расскажи о {topic} в истории России (глава 3). Сосредоточься на ключевых фигурах, реформах и внутренней политике. Объем - один абзац. Не пиши 'продолжение следует'.",
            f"Расскажи о {topic} в истории России (глава 4). Опиши внешнюю политику, международное влияние и связи. Объем - один абзац. Не пиши 'продолжение следует'.",
            f"Расскажи о {topic} в истории России (глава 5). Опиши итоги, значение в истории и культуре, последствия. Заверши повествование. Объем - один абзац."
        ]

        # Оптимизация: параллельная обработка запросов к API (используем нативные потоки)
        all_responses = [""] * len(prompts)
        threads = []

        def fetch_response(index, prompt):
            if update_message_func:
                update_message_func(f"📝 Загружаю главу {index+1} из {len(prompts)} по теме: *{topic}*...")

            # Получаем ответ от API с использованием общего кэша
            response = self.api_client.ask_grok(prompt)

            # Добавляем заголовок главы перед текстом
            chapter_response = f"*{chapter_titles[index]}*\n\n{response}"
            all_responses[index] = chapter_response

        # Создаем и запускаем потоки
        for i, prompt in enumerate(prompts):
            thread = threading.Thread(target=fetch_response, args=(i, prompt))
            thread.start()
            threads.append(thread)
            # Добавляем небольшую задержку для разгрузки API
            time.sleep(0.5)

        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()

        # Объединяем ответы с разделителями
        combined_responses = "\n\n" + "\n\n".join(all_responses)

        # Оптимизированный алгоритм разделения на части (макс. 4000 символов) для отправки в Telegram
        messages = []
        max_length = 4000

        # Эффективный алгоритм разделения на части с сохранением форматирования markdown
        current_part = ""
        paragraphs = combined_responses.split('\n\n')

        for paragraph in paragraphs:
            if paragraph.startswith('*') and current_part and len(current_part) + len(paragraph) + 2 > max_length:
                # Начало новой главы, сохраняем предыдущую часть
                messages.append(current_part)
                current_part = paragraph
            elif len(current_part) + len(paragraph) + 2 > max_length:
                # Превышение лимита, сохраняем текущую часть
                messages.append(current_part)
                current_part = paragraph
            else:
                # Добавляем абзац к текущей части
                if current_part:
                    current_part += '\n\n' + paragraph
                else:
                    current_part = paragraph

        # Добавляем последнюю часть, если она не пуста
        if current_part:
            messages.append(current_part)

        return messages
    
    def generate_test(self, topic):
        """Генерирует тест по заданной теме"""
        prompt = f"Составь 15 вопросов с вариантами ответа (1, 2, 3, 4) по теме '{topic}' в истории России. После каждого вопроса с вариантами ответов укажи правильный ответ в формате 'Правильный ответ: <цифра>'. Каждый вопрос должен заканчиваться строкой '---'."
        try:
            # Увеличиваем лимит токенов для получения полных вопросов
            questions = self.api_client.ask_grok(prompt, max_tokens=2048)

            # Очистка и валидация вопросов
            question_list = [q.strip() for q in questions.split('---') if q.strip()]

            # Проверка наличия правильных ответов в каждом вопросе
            valid_questions = []
            for q in question_list:
                if 'Правильный ответ:' in q:
                    valid_questions.append(q)

            if not valid_questions:
                raise ValueError("Не удалось сгенерировать корректные вопросы для теста")

            # Очищаем правильные ответы из текста вопросов для отображения пользователю
            display_questions = []
            for q in valid_questions:
                # Удаляем строку с правильным ответом из текста вопроса
                cleaned_q = re.sub(r"Правильный ответ:\s*\d+", "", q).strip()
                display_questions.append(cleaned_q)

            return {
                'original_questions': valid_questions,
                'display_questions': display_questions
            }
        except Exception as e:
            self.logger.error(f"Ошибка при генерации теста: {e}")
            raise e


import threading
import re
import random
import time
from src.interfaces import IContentProvider

class ContentService(IContentProvider):
    """Класс для обработки и получения образовательного контента"""
    
    def __init__(self, api_client, logger):
        self.api_client = api_client
        self.logger = logger
    
    def get_topic_info(self, topic, update_message_func=None):
        """
        Получает информацию о теме из API с оптимизированной параллельной загрузкой и обработкой.

        Args:
            topic (str): Тема для изучения
            update_message_func (callable, optional): Функция для обновления сообщения о загрузке

        Returns:
            list: Список сообщений для отправки
        """
        # Используем tupple для неизменяемости и более эффективного доступа к памяти
        chapter_titles = (
            "📜 ВВЕДЕНИЕ И ИСТОКИ",
            "⚔️ ОСНОВНЫЕ СОБЫТИЯ И РАЗВИТИЕ",
            "🏛️ КЛЮЧЕВЫЕ ФИГУРЫ И РЕФОРМЫ",
            "🌍 ВНЕШНЯЯ ПОЛИТИКА И ВЛИЯНИЕ",
            "📊 ИТОГИ И ИСТОРИЧЕСКОЕ ЗНАЧЕНИЕ"
        )

        # Формируем более короткие запросы для снижения нагрузки на API и увеличения скорости
        prompts = (
            f"Расскажи о {topic} в истории России. Введение и истоки. Один абзац.",
            f"Расскажи о {topic} в истории России. Основные события и развитие. Один абзац.",
            f"Расскажи о {topic} в истории России. Ключевые фигуры и реформы. Один абзац.",
            f"Расскажи о {topic} в истории России. Внешняя политика и влияние. Один абзац.",
            f"Расскажи о {topic} в истории России. Итоги и значение. Один абзац."
        )

        # Используем ThreadPoolExecutor вместо ручного управления потоками
        # для более эффективного выполнения параллельных задач
        all_responses = [""] * len(prompts)
        from concurrent.futures import ThreadPoolExecutor

        def fetch_response(args):
            index, prompt = args
            if update_message_func and index % 2 == 0:  # Сокращаем обновления до 3 раз для снижения нагрузки
                update_message_func(f"📝 Загружаю главы по теме: *{topic}*... {index+1}/{len(prompts)}")

            # Получаем ответ от API с использованием общего кэша и ограничением токенов
            response = self.api_client.ask_grok(prompt, max_tokens=500)
            # Добавляем заголовок главы перед текстом
            return f"*{chapter_titles[index]}*\n\n{response}"

        # Используем ThreadPoolExecutor для более эффективного управления потоками
        # Ограничиваем количество одновременных запросов до 3 для снижения нагрузки на API
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Используем enumerate для создания кортежей (index, prompt)
            responses = list(executor.map(fetch_response, enumerate(prompts)))
        
        # Объединяем ответы с разделителями - оптимизируем для избежания множественной конкатенации
        combined_responses = "\n\n" + "\n\n".join(responses)

        # Улучшенный алгоритм разделения на части с предварительным расчетом размеров
        messages = []
        max_length = 4000
        
        # Используем алгоритм жадного разделения с учетом маркдаун заголовков
        current_part = ""
        chapter_starts = []
        
        # Предварительно находим все начала глав для оптимального разделения
        paragraphs = combined_responses.split('\n\n')
        for i, paragraph in enumerate(paragraphs):
            if paragraph.startswith('*'):
                chapter_starts.append(i)
        
        # Добавляем индекс конца для упрощения алгоритма
        chapter_starts.append(len(paragraphs))
        
        # Собираем сообщения по главам с учетом ограничений размера
        start_idx = 0
        for end_idx in chapter_starts[1:]:
            chapter_content = '\n\n'.join(paragraphs[start_idx:end_idx])
            
            # Если глава целиком помещается в лимит
            if len(chapter_content) <= max_length:
                if current_part and len(current_part) + len(chapter_content) + 2 > max_length:
                    messages.append(current_part)
                    current_part = chapter_content
                else:
                    if current_part:
                        current_part += '\n\n' + chapter_content
                    else:
                        current_part = chapter_content
            else:
                # Глава не помещается целиком, разбиваем на части
                if current_part:
                    messages.append(current_part)
                    current_part = ""
                
                # Разбиваем большую главу на части
                temp_paragraphs = chapter_content.split('\n\n')
                temp_part = ""
                
                for para in temp_paragraphs:
                    if len(temp_part) + len(para) + 2 > max_length:
                        messages.append(temp_part)
                        temp_part = para
                    else:
                        if temp_part:
                            temp_part += '\n\n' + para
                        else:
                            temp_part = para
                
                if temp_part:
                    current_part = temp_part
            
            start_idx = end_idx
        
        # Добавляем последнюю часть
        if current_part:
            messages.append(current_part)

        return messages
    
    def generate_test(self, topic):
        """Генерирует тест по заданной теме с оптимизацией"""
        # Уменьшаем количество запрашиваемых вопросов для снижения нагрузки
        prompt = f"Составь 10 вопросов с вариантами ответа (1, 2, 3, 4) по теме '{topic}' в истории России. После каждого вопроса с вариантами ответов укажи правильный ответ в формате 'Правильный ответ: <цифра>'. Каждый вопрос должен заканчиваться строкой '---'."
        try:
            # Оптимизируем запрос, используем кэш если возможно
            questions = self.api_client.ask_grok(prompt, max_tokens=1500, temp=0.2)

            # Используем более эффективное разделение вопросов
            question_list = [q.strip() for q in questions.split('---') if q.strip()]
            
            # Оптимизированная фильтрация валидных вопросов
            valid_questions = []
            display_questions = []
            
            regexp = re.compile(r"Правильный ответ:\s*(\d+)")
            
            for q in question_list:
                if 'Правильный ответ:' in q:
                    valid_questions.append(q)
                    # Сразу создаем очищенный вопрос для отображения
                    cleaned_q = regexp.sub("", q).strip()
                    display_questions.append(cleaned_q)
            
            # Проверка наличия достаточного количества вопросов
            if len(valid_questions) < 5:
                raise ValueError("Недостаточно корректных вопросов для теста")

            return {
                'original_questions': valid_questions,
                'display_questions': display_questions
            }
        except Exception as e:
            self.logger.error(f"Ошибка при генерации теста: {e}")
            # Пробуем запросить меньше вопросов при ошибке
            try:
                fallback_prompt = f"Составь 5 вопросов с вариантами ответа (1, 2, 3, 4) по теме '{topic}' в истории России. После каждого вопроса укажи 'Правильный ответ: <цифра>'."
                questions = self.api_client.ask_grok(fallback_prompt, max_tokens=800, temp=0.1)
                
                # Минимальная обработка
                valid_questions = [q for q in questions.split('\n\n') if 'Правильный ответ:' in q]
                display_questions = [re.sub(r"Правильный ответ:\s*\d+", "", q).strip() for q in valid_questions]
                
                return {
                    'original_questions': valid_questions,
                    'display_questions': display_questions
                }
            except:
                raise e  # Если и резервный вариант не сработал, пробрасываем исходную ошибку

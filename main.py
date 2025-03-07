
import os
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import logging
import datetime
import requests
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Создание объекта логгера
logger = logging.getLogger(__name__)

# Настройка файлового хендлера для логирования
def setup_file_logger():
    # Создаем директорию для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Получаем текущую дату для имени файла
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    log_file = f'logs/bot_log_{current_date}.log'
    
    # Создаем хендлер для записи в файл
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    file_handler.setLevel(logging.INFO)
    
    # Добавляем хендлер к логгеру
    logger.addHandler(file_handler)
    logger.info(f"Логирование настроено в файл: {log_file}")

# Настройка API ключа Google Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    logger.error("Отсутствует GEMINI_API_KEY в файле .env")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# Глобальный кэш для хранения контекста разговора с пользователями
user_contexts = {}

# Получение токена Telegram бота из переменной окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.error("Отсутствует TELEGRAM_TOKEN в файле .env")
    exit(1)

# Функция для вызова Gemini API с моделью 2.0 Flash
def ask_grok(prompt, max_tokens=1024, temp=0.7):
    """
    Отправляет запрос к API Gemini 2.0 Flash и возвращает ответ.

    Args:
        prompt (str): Промпт для отправки
        max_tokens (int): Максимальное количество токенов в ответе
        temp (float): Температура (креативность) генерации

    Returns:
        str: Текст ответа от API
    """
    try:
        # Конфигурация модели
        generation_config = {
            "temperature": temp,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": max_tokens,
        }

        # Создание модели с заданной конфигурацией, используя Gemini 2.0 Flash
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # Используем модель 2.0 Flash для более быстрой обработки
            generation_config=generation_config
        )

        # Отправка запроса и получение ответа
        response = model.generate_content(prompt)
        
        # Проверка, есть ли ответ
        if not response or not response.text:
            logger.error(f"API вернул ответ без содержимого: {response}")
            return "Извините, произошла ошибка при генерации ответа. Пожалуйста, попробуйте еще раз."
        
        return response.text
    except Exception as e:
        logger.error(f"Ошибка при вызове API Gemini: {e}")
        return f"Произошла ошибка: {e}"

# Исторические периоды и события для меню
HISTORICAL_PERIODS = {
    "ancient_rus": "Древняя Русь (IX-XIII века)",
    "mongol_invasion": "Монгольское нашествие (XIII-XV века)",
    "moscow_state": "Московское государство (XV-XVII века)",
    "russian_empire": "Российская империя (XVIII-XX века)",
    "revolution": "Революция и Гражданская война (1917-1922)",
    "soviet_union": "СССР (1922-1991)",
    "modern_russia": "Современная Россия (с 1991)"
}

# Важные исторические личности
HISTORICAL_FIGURES = {
    "rurik": "Рюрик",
    "vladimir": "Владимир Великий",
    "nevsky": "Александр Невский",
    "ivan_terrible": "Иван Грозный",
    "peter_great": "Пётр I Великий",
    "catherine_great": "Екатерина II Великая",
    "alexander_ii": "Александр II Освободитель",
    "nicholas_ii": "Николай II",
    "lenin": "В.И. Ленин",
    "stalin": "И.В. Сталин",
    "khrushchev": "Н.С. Хрущёв",
    "gorbachev": "М.С. Горбачёв",
    "yeltsin": "Б.Н. Ельцин",
    "putin": "В.В. Путин"
}

# Функция для создания главного меню
def get_main_menu_keyboard():
    """Создает главное меню бота"""
    keyboard = [
        [InlineKeyboardButton("🏛 Исторические периоды", callback_data='periods')],
        [InlineKeyboardButton("👑 Исторические личности", callback_data='figures')],
        [InlineKeyboardButton("🎓 Тесты по истории", callback_data='tests')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Функция для создания меню периодов
def get_periods_keyboard():
    """Создает меню выбора исторического периода"""
    keyboard = []
    for period_id, period_name in HISTORICAL_PERIODS.items():
        keyboard.append([InlineKeyboardButton(period_name, callback_data=f'period_{period_id}')])
    keyboard.append([InlineKeyboardButton("◀️ Назад в главное меню", callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

# Функция для создания меню исторических личностей
def get_figures_keyboard():
    """Создает меню выбора исторической личности"""
    keyboard = []
    row = []
    for i, (figure_id, figure_name) in enumerate(HISTORICAL_FIGURES.items()):
        row.append(InlineKeyboardButton(figure_name, callback_data=f'figure_{figure_id}'))
        if (i + 1) % 2 == 0 or i == len(HISTORICAL_FIGURES) - 1:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("◀️ Назад в главное меню", callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

# Функция для создания меню тестов
def get_tests_keyboard():
    """Создает меню тестов"""
    keyboard = [
        [InlineKeyboardButton("🧠 Базовый тест (10 вопросов)", callback_data='test_basic')],
        [InlineKeyboardButton("🔬 Продвинутый тест (20 вопросов)", callback_data='test_advanced')],
        [InlineKeyboardButton("🎯 Тест по конкретному периоду", callback_data='test_period')],
        [InlineKeyboardButton("◀️ Назад в главное меню", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Функция для создания клавиатуры для выбора периода для теста
def get_test_periods_keyboard():
    """Создает меню выбора периода для теста"""
    keyboard = []
    for period_id, period_name in HISTORICAL_PERIODS.items():
        keyboard.append([InlineKeyboardButton(period_name, callback_data=f'test_period_{period_id}')])
    keyboard.append([InlineKeyboardButton("◀️ Назад к тестам", callback_data='tests')])
    return InlineKeyboardMarkup(keyboard)

# Функция для обработки команды /start
def start(update, context):
    """Обрабатывает команду /start"""
    # Получаем информацию о пользователе
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")
    
    # Приветственное сообщение
    welcome_message = (
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        "Добро пожаловать в бота по истории России! 🇷🇺\n\n"
        "Я помогу вам изучить ключевые события, исторические периоды "
        "и выдающихся личностей российской истории.\n\n"
        "Выберите интересующий вас раздел в меню ниже:"
    )
    
    # Отправляем приветственное сообщение с главным меню
    update.message.reply_text(welcome_message, reply_markup=get_main_menu_keyboard())

# Функция для обработки нажатий на кнопки
def button_handler(update, context):
    """Обрабатывает нажатия на кнопки меню"""
    query = update.callback_query
    query.answer()  # Отвечаем на callback запрос
    
    user_id = query.from_user.id
    callback_data = query.data
    logger.info(f"Пользователь {user_id} нажал кнопку: {callback_data}")
    
    # Обработка выбора в главном меню
    if callback_data == 'main_menu':
        query.edit_message_text(
            "Выберите интересующий вас раздел:",
            reply_markup=get_main_menu_keyboard()
        )
    
    # Обработка выбора в меню периодов
    elif callback_data == 'periods':
        query.edit_message_text(
            "Выберите исторический период, чтобы узнать о нём подробнее:",
            reply_markup=get_periods_keyboard()
        )
    
    # Обработка выбора периода
    elif callback_data.startswith('period_'):
        period_id = callback_data.replace('period_', '')
        period_name = HISTORICAL_PERIODS.get(period_id, "Неизвестный период")
        
        # Формируем запрос к API для получения информации о периоде
        prompt = (
            f"Расскажи подробно об историческом периоде России: {period_name}.\n"
            "Включи ключевые события, даты, исторические процессы и их значение для истории России.\n"
            "Структурируй информацию по хронологии, выдели важнейшие события и личности периода.\n"
            "Информация должна быть исторически точной и объективной."
        )
        
        # Отправляем сообщение о загрузке
        query.edit_message_text(f"⏳ Загружаю информацию о периоде «{period_name}»...")
        
        # Получаем ответ от API
        response = ask_grok(prompt, max_tokens=2048, temp=0.3)
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ К списку периодов", callback_data='periods')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем информацию о периоде
        query.edit_message_text(
            f"*{period_name}*\n\n{response}",
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Обработка выбора в меню исторических личностей
    elif callback_data == 'figures':
        query.edit_message_text(
            "Выберите историческую личность, чтобы узнать о ней подробнее:",
            reply_markup=get_figures_keyboard()
        )
    
    # Обработка выбора исторической личности
    elif callback_data.startswith('figure_'):
        figure_id = callback_data.replace('figure_', '')
        figure_name = HISTORICAL_FIGURES.get(figure_id, "Неизвестная личность")
        
        # Формируем запрос к API для получения информации о личности
        prompt = (
            f"Расскажи подробно об исторической личности России: {figure_name}.\n"
            "Включи биографию, ключевые даты, достижения, историческое значение и влияние на историю России.\n"
            "Структурируй информацию, выделив основные этапы жизни и деятельности.\n"
            "Информация должна быть исторически точной и объективной."
        )
        
        # Отправляем сообщение о загрузке
        query.edit_message_text(f"⏳ Загружаю информацию о личности «{figure_name}»...")
        
        # Получаем ответ от API
        response = ask_grok(prompt, max_tokens=1800, temp=0.3)
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ К списку личностей", callback_data='figures')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем информацию о личности
        query.edit_message_text(
            f"*{figure_name}*\n\n{response}",
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Обработка выбора в меню тестов
    elif callback_data == 'tests':
        query.edit_message_text(
            "Выберите тип теста по истории России:",
            reply_markup=get_tests_keyboard()
        )
    
    # Обработка выбора теста по периоду
    elif callback_data == 'test_period':
        query.edit_message_text(
            "Выберите исторический период для теста:",
            reply_markup=get_test_periods_keyboard()
        )
    
    # Обработка выбора периода для теста
    elif callback_data.startswith('test_period_'):
        period_id = callback_data.replace('test_period_', '')
        period_name = HISTORICAL_PERIODS.get(period_id, "Неизвестный период")
        
        # Формируем запрос к API для генерации теста
        prompt = (
            f"Создай тест по истории России на тему: {period_name}.\n"
            "Тест должен содержать 5 вопросов с разным уровнем сложности.\n"
            "Каждый вопрос должен иметь 4 варианта ответа, один из которых является правильным.\n"
            "Пометь правильный ответ знаком (✓).\n"
            "Вопросы должны касаться ключевых событий, личностей и процессов периода.\n"
            "В конце приведи краткую информацию об исторической значимости этого периода."
        )
        
        # Отправляем сообщение о загрузке
        query.edit_message_text(f"⏳ Генерирую тест по периоду «{period_name}»...")
        
        # Получаем ответ от API
        response = ask_grok(prompt, max_tokens=2048, temp=0.7)
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ К выбору тестов", callback_data='tests')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сгенерированный тест
        query.edit_message_text(
            f"*Тест по истории России: {period_name}*\n\n{response}",
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Обработка выбора базового теста
    elif callback_data == 'test_basic':
        # Формируем запрос к API для генерации теста
        prompt = (
            "Создай базовый тест по истории России.\n"
            "Тест должен содержать 10 вопросов с базовым уровнем сложности, охватывающих разные периоды истории России.\n"
            "Каждый вопрос должен иметь 4 варианта ответа, один из которых является правильным.\n"
            "Пометь правильный ответ знаком (✓).\n"
            "Вопросы должны касаться ключевых событий, дат, личностей и процессов истории России."
        )
        
        # Отправляем сообщение о загрузке
        query.edit_message_text("⏳ Генерирую базовый тест по истории России...")
        
        # Получаем ответ от API
        response = ask_grok(prompt, max_tokens=2048, temp=0.7)
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ К выбору тестов", callback_data='tests')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сгенерированный тест
        query.edit_message_text(
            "*Базовый тест по истории России*\n\n{response}",
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Обработка выбора продвинутого теста
    elif callback_data == 'test_advanced':
        # Формируем запрос к API для генерации теста
        prompt = (
            "Создай продвинутый тест по истории России.\n"
            "Тест должен содержать 20 вопросов повышенной сложности, охватывающих разные периоды истории России.\n"
            "Каждый вопрос должен иметь 4 варианта ответа, один из которых является правильным.\n"
            "Пометь правильный ответ знаком (✓).\n"
            "Вопросы должны содержать детали, менее известные факты и требовать глубокого знания истории России."
        )
        
        # Отправляем сообщение о загрузке
        query.edit_message_text("⏳ Генерирую продвинутый тест по истории России...")
        
        # Получаем ответ от API
        response = ask_grok(prompt, max_tokens=2048, temp=0.7)
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ К выбору тестов", callback_data='tests')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сгенерированный тест
        query.edit_message_text(
            "*Продвинутый тест по истории России*\n\n{response}",
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Обработка выбора статистики
    elif callback_data == 'stats':
        # Заглушка для статистики (в будущем здесь будет реальная статистика)
        stats_message = (
            "*Статистика использования бота*\n\n"
            "📊 Функция находится в разработке и будет доступна в следующих обновлениях.\n\n"
            "В будущих версиях здесь будет отображаться:\n"
            "• Количество пройденных тестов\n"
            "• Результаты и прогресс\n"
            "• Наиболее популярные темы\n"
            "• Персональные рекомендации\n\n"
            "Следите за обновлениями!"
        )
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ Назад в главное меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            stats_message,
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Обработка выбора информации о боте
    elif callback_data == 'about':
        about_message = (
            "*О боте «История России»*\n\n"
            "🤖 Этот бот создан для изучения истории России в интерактивном формате.\n\n"
            "Возможности бота:\n"
            "• Информация об исторических периодах\n"
            "• Биографии исторических личностей\n"
            "• Тесты разной сложности\n"
            "• Интерактивное взаимодействие\n\n"
            "Бот использует технологии искусственного интеллекта от Google Gemini для генерации контента.\n\n"
            "📝 Задайте любой вопрос по истории России, и бот постарается на него ответить!\n\n"
            "🔄 Версия: 1.0 (Март 2025)"
        )
        
        # Добавляем кнопку возврата
        keyboard = [[InlineKeyboardButton("◀️ Назад в главное меню", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            about_message,
            parse_mode=telegram.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

# Функция для обработки текстовых сообщений
def handle_message(update, context):
    """Обрабатывает текстовые сообщения от пользователя"""
    # Получаем информацию о пользователе и сообщении
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"Получено сообщение от {user.id} ({user.username}): {message_text[:50]}" + ("..." if len(message_text) > 50 else ""))
    
    # Проверяем длину сообщения
    if len(message_text) > 500:
        update.message.reply_text(
            "❗ Ваше сообщение слишком длинное. Пожалуйста, ограничьтесь 500 символами.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Проверяем, относится ли вопрос к истории России
    check_prompt = f"Проверь, относится ли следующий вопрос к истории России: \"{message_text}\". Ответь только 'да' или 'нет'."
    is_history_related = ask_grok(check_prompt, max_tokens=50, temp=0.1).lower().strip()
    
    # Если вопрос не относится к истории России
    if 'нет' in is_history_related:
        update.message.reply_text(
            "⚠️ Я специализируюсь только на истории России.\n\n"
            "Пожалуйста, задайте вопрос, связанный с историей России, "
            "или воспользуйтесь меню для выбора интересующей вас темы.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Отправляем индикатор набора текста
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.ChatAction.TYPING)
    
    # Формируем промпт для ответа на вопрос
    prompt = (
        f"Ответь на следующий вопрос по истории России: \"{message_text}\"\n\n"
        "Твой ответ должен быть:\n"
        "1. Исторически точным и основанным на фактах\n"
        "2. Информативным и содержательным\n"
        "3. Хорошо структурированным\n"
        "4. С упоминанием ключевых дат, имен и событий\n\n"
        "Ответ должен быть понятен человеку без специальных знаний по истории."
    )
    
    # Получаем ответ от API
    response = ask_grok(prompt, max_tokens=1800, temp=0.3)
    
    # Отправляем ответ пользователю с кнопкой перехода в главное меню
    keyboard = [[InlineKeyboardButton("◀️ Вернуться в главное меню", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        response,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN
    )

def main():
    """Главная функция для запуска бота"""
    # Настройка логирования в файл
    setup_file_logger()
    logger.info("Бот запускается...")
    
    # Создаем объект Updater и передаем ему токен бота
    updater = Updater(TELEGRAM_TOKEN)
    
    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher
    
    # Регистрируем обработчики команд
    dp.add_handler(CommandHandler("start", start))
    
    # Регистрируем обработчик нажатий на кнопки
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Регистрируем обработчик текстовых сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    updater.start_polling()
    
    # Останавливаем бота, если нажаты Ctrl+C
    updater.idle()

if __name__ == '__main__':
    main()

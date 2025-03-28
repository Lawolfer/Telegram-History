
# Система кэширования

## Обзор

Проект использует многоуровневую систему кэширования для оптимизации производительности и снижения количества запросов к API. Система кэширования состоит из нескольких компонентов, каждый из которых отвечает за определенную часть функциональности.

## Компоненты кэширования

### 1. APICache

**Файл:** `src/api_cache.py`

**Назначение:** Кэширование API запросов к Gemini API для снижения количества обращений и ускорения ответов.

**Особенности:**
- Персистентное хранение в JSON-файле
- Механизм истечения срока действия (TTL)
- Стратегия вытеснения LRU (Least Recently Used)
- Ограничение размера кэша
- Сбор статистики использования кэша

**Основные методы:**
- `get(key)` - Получение значения из кэша
- `set(key, value, ttl)` - Установка значения в кэш с временем жизни
- `remove(key)` - Удаление элемента из кэша
- `clear()` - Очистка всего кэша
- `get_stats()` - Получение статистики использования

### 2. TextCacheService

**Файл:** `src/text_cache_service.py`

**Назначение:** Кэширование сгенерированных текстов для повторного использования, включая информацию о темах и тестовые задания.

**Особенности:**
- Организация кэша по типам контента (темы, тесты)
- Версионирование кэшированных данных
- Метрики актуальности кэша

**Основные методы:**
- `get_text(topic, text_type)` - Получение текста из кэша
- `save_text(topic, text_type, text)` - Сохранение текста в кэш
- `clear_cache(topic_filter)` - Очистка кэша по фильтру
- `get_stats()` - Получение статистики использования

### 3. DistributedCache (опционально)

**Файл:** `src/distributed_cache.py`

**Назначение:** Распределенное кэширование для работы в многосерверной среде.

**Особенности:**
- Поддержка различных бэкендов (Memory, Redis)
- Автоматическая синхронизация между узлами
- Защита от гонок данных

## Стратегии кэширования

### Стратегия для API запросов

1. **Время жизни кэша (TTL):**
   - Короткое TTL (1 час) для часто меняющихся данных
   - Длительное TTL (24 часа) для стабильных данных (исторический контент)

2. **Ключи кэша:**
   - Хеш от комбинации параметров запроса (prompt + temperature + max_tokens)
   - Префикс для разных типов запросов

3. **Стратегия инвалидации:**
   - Естественное истечение TTL
   - Принудительная очистка при обновлении данных
   - Временная метка для проверки актуальности

### Стратегия для текстового контента

1. **Структура кэша:**
   - Иерархическая: тема -> тип контента -> содержимое
   
2. **Приоритизация кэша:**
   - Кэширование популярных тем с более длительным TTL
   - Динамическая регулировка TTL на основе частоты запросов

3. **Мониторинг:**
   - Отслеживание hit/miss ratio
   - Адаптивная настройка параметров кэша

## Управление кэшем

### Инструменты администратора

1. **Очистка кэша:**
   - Полная очистка для обновления всего контента
   - Селективная очистка по темам для обновления конкретного контента
   
2. **Просмотр статистики:**
   - Процент попаданий (hit rate)
   - Эффективность использования памяти
   - Распределение запросов по типам

### API кэш-менеджмента

```python
# Пример использования API для управления кэшем
cache_manager = CacheManager()

# Получить статистику
stats = cache_manager.get_stats()

# Очистить кэш по теме
cache_manager.clear_cache(topic_filter="Великая Отечественная война")

# Предварительно заполнить кэш часто запрашиваемыми темами
cache_manager.prefill_popular_topics()
```

## Оптимизация и улучшения

1. **Компрессия данных** для уменьшения занимаемого пространства
2. **Частичная инвалидация** для обновления только устаревших частей данных
3. **Предварительное заполнение** кэша популярными запросами
4. **Адаптивный TTL** на основе частоты использования данных
5. **Многоуровневый кэш** с быстрой памятью для горячих данных и медленным хранилищем для холодных

## Мониторинг и обслуживание

1. **Регулярная очистка** устаревших данных
2. **Резервное копирование** кэша для предотвращения потери данных
3. **Анализ паттернов использования** для оптимизации стратегии кэширования
4. **Автоматическая регенерация** кэша для популярных запросов

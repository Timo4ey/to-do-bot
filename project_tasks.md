# 📋 Audio To Do — список задач

## ✅ Уже реализовано
- [x] Обработка аудио (merge, поддержка MP3/WAV/OGG)
- [x] Команда `/start`: приветствие и вводное сообщение
- [x] Команда `/распознать`: загрузка аудио + выбор режима
- [x] Retry на ошибки STT/LLM: 3 попытки (15s, 60s, 120s)
- [x] Настроены `.env`: `SBER_API_KEY`, `GIGACHAT_API_KEY`, `RABBITMQ_URL`

---

## 🧠 Архитектура и конфигурация
- [ ] Добавить в `.env` переменные для БД (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`)
- [ ] Добавить `/health` endpoint для:
  - [ ] Worker
  - [ ] Bot
- [ ] Настроить `docker-compose.yml`:
  - [ ] Добавить все сервисы
  - [ ] Установить `restart: on-failure`
  - [ ] Задать `deploy.resources.limits` (CPU, RAM)

---

## 🤖 Telegram Bot (aiogram)
- [ ] Middleware:
  - [ ] Ограничение RPS (антифлуд)
  - [ ] Опционально: whitelist-авторизация
- [ ] Получение статуса задачи из `task_status_queue`
- [ ] Отправка результата пользователю в Markdown-формате

---

## 🪄 Task Queue (RabbitMQ)
- [ ] Настроить очереди:
  - [ ] `audio_tasks_exchange` (direct)
  - [ ] `audio_tasks_queue`
  - [ ] `task_status_queue`
  - [ ] `audio_tasks_dlq`
- [ ] Отправка задач из бота в очередь
- [ ] Получение статуса задачи из очереди

---

## 👷 Worker (pipeline)
- [ ] Обновление задачи в Postgres:
  - [ ] `Finished`, `Failed`
- [ ] Публикация статуса в `task_status_queue`

---

## 🗄 Хранение результатов
- [ ] Создать таблицы:
  - [ ] `users`
  - [ ] `tasks`
- [ ] Реализовать доступ (`store.py`):
  - [ ] `create_task()`
  - [ ] `update_task()`
  - [ ] `get_user_tasks()`
- [ ] Хранить только текст и `metadata`, не сохранять аудио

---

## 📊 Мониторинг и логирование
- [ ] Интеграция с Prometheus:
  - [ ] Метрики: RPS, ошибки, время обработки
- [ ] Grafana:
  - [ ] Базовая панель с RPS и ошибками
- [ ] logging:
  - [ ] INFO, ERROR, traceback

---

## 🧪 Тестирование
- [ ] Юнит-тесты:
  - [ ] `store.py`
  - [ ] `llm.py`
  - [ ] `salute_speech_stt.py`
- [ ] Интеграционные тесты:
  - [ ] Пайплайн end-to-end (бот → очередь → STT/LLM → результат)
- [ ] Моки внешних API:
  - [ ] STT (Sber)
  - [ ] LLM (GigaChat)
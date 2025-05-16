**Audio To DO — Telegram-бот**

---

## 1. Введение

* **Ключевые сценарии использования**:

  * **Пользовательский**: человек отправляет голосовое сообщение с задачами и получает структурированный список To-Do, пригодный для переноса в таск-трекеры.
  * **Бизнес-сценарий**: саммаризация ключевых мыслей созвона или рабочего дня без необходимости ручного конспектирования.

* **Цель проекта**: предоставить пользователям удобный способ из устных заметок получать структурированный список задач или саммари прошедшего дня.

* **Основные характеристики**:

  * Поддержка форматов: WAV, MP3, OGG
  * Выбор режима: задачи / саммаризация
  * Без хранения исходных аудио, сохраняются лишь результаты
  * Публичный бот в Telegram
  * RPS до 10, длительность аудио ≤ 30 минут
  * Язык: русский с англицизмами

## 2. Требования

### 2.1 Функциональные

* Загрузка одного или нескольких аудио-файлов
* Объединение и предобработка (склейка) аудио
* Запрос режима (список задач / саммаризация)
* Обработка через STT (Sber Salute) + LRO
* Отправка текста в LLM (Sber GigaChat через LangChain)
* Отправка результата в виде Markdown
* Хранение истории результатов для пользователя

### 2.2 Нефункциональные

* **Язык**: Python 3.9+
* Асинхронность: aiohttp / aiogram
* **RPS**: до 10
* **SLA**: задержка не критична, но с уведомлением о состоянии «В обработке»
* **Метрики**: время обработки, ошибки, RPS, загрузка очередей (Prometheus + Grafana)
* **Retry**: механизм ретраев при сбоях STT/LLM
* **Деплой**: Docker Compose на VPS

## 3. Обзор архитектуры

> Также предусмотрены middleware-компоненты в aiogram, отвечающие за авторизацию и ограничение доступа, включая защиту от флуда для публичного Telegram-бота.

```
[Telegram Bot] ⇄ [API Gateway / aiogram] ⇄ [Task Queue]
                                 │
                                 ▼
                            [Worker Pool]
                                 │
           ┌─────────────┬───────┴────────┬─────────────┐
           │             │                │             │
     [Audio Merger] [STT Client]     [LLM Client] [Results Storage]
           │             │                │             │
           └─────────────┴────────────────┴─────────────┘
                                 │
                                 ▼
                         [Telegram Bot: Result Delivery]
```

## 4. Компоненты и взаимодействие

> Также следует предусмотреть явное описание компонентов, отвечающих за авторизацию и ограничение доступа, таких как middleware в aiogram, обеспечивающих защиту от флуда и контроля доступа к функциям бота. Также рекомендуется задать таймауты HTTP-запросов к внешним сервисам (STT, LLM) и реализовать fallback-логику или уведомления пользователю при недоступности этих провайдеров.

1. **Telegram Bot (aiogram)**

   * Обработка `/start`, загрузка аудио и выбор режима
   * Команда `Распознать` → создание записи в БД, публикация задачи в очередь
   * Уведомления: «Запрос принят», «В обработке», «Готово»

2. **Task Queue (RabbitMQ)**

   * Обменник `audio_tasks_exchange` (type: direct)
   * Очереди:

     * `audio_tasks_queue` (routing\_key `audio_tasks`)
     * `task_status_queue` (статусы Finished/Failed)
     * DLQ: `audio_tasks_dlq`

3. **Worker Pool**

   * asyncio + aiohttp, 1 реплика для RPS=10
   * Пайплайн: merge → stt → llm → store → notify
   * Health-check: `/health` endpoint

4. **Audio Merger**

   * Склейка нескольких аудио в единый файл

5. **STT Client**

   * Sber Salute LRO API
   * До 3 попыток с backoff: 15s, 60s, 120s

6. **LLM Client (LangChain)**

   * Sber GigaChat через langchain-gigachat
   * Подбор системного промпта по режиму

7. **Results Storage (Postgres)**

   * Таблица `users` и `tasks`

8. **Monitoring & Logging**

   * Prometheus + Grafana
   * logging: INFO, ERROR

## 5. Сценарий обработки

1. Пользователь отправляет аудио + режим + `/Распознать`.
2. Bot сохраняет запись задачи (state=Pending) и отвечает «Запрос принят».
3. Задача попадает в `audio_tasks_queue`.
4. Worker забирает задачу (state=Running).
5. Merge → STT → LLM → сохранение результата в `tasks` (state=Finished или Failed).
6. Публикация статуса в `task_status_queue`.
7. Bot получает статус и отправляет Markdown-результат.

## 6. Технологический стек

* **Python** 3.9+
* **aiogram**, **aiohttp**
* **RabbitMQ**, **Postgres**
* **Sber Salute STT**, **Sber GigaChat** через LangChain
* **Prometheus**, **Grafana**
* **Docker Compose**

## 7. LLD: Схема БД и конфигурация

### 7.1 SQL-схема

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  user_id BIGINT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
  id SERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(user_id),
  task_type VARCHAR(16) NOT NULL CHECK (task_type IN ('stt','llm')),
  result TEXT,
  state VARCHAR(16) NOT NULL CHECK (state IN ('Pending','Running','Finished','Failed')),
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 7.2 Конфигурация и секреты

* `.env` или Vault:

  ```env
  SBER_API_KEY=...
  GIGACHAT_API_KEY=...
  RABBITMQ_URL=amqp://user:pass@rabbitmq:5672/
  ```

### 7.3 Retry и DLQ

* 3 попытки (15s, 60s, 120s)
* DLQ `audio_tasks_dlq` для задач с 3 ошибками

### 7.4 Логи и мониторинг

* logging (INFO, ERROR)
* `/health` endpoint

### 7.5 Тестирование

* Unit-тесты (pytest, моки Sber)
* Интеграционные тесты (RabbitMQ, Postgres)

## 8. Docker Compose

> Рекомендуется указать для контейнеров параметры `restart: on-failure` и задать ограничения ресурсов (`deploy.resources.limits`) для повышения устойчивости работы на VPS, особенно в условиях ограниченного объема памяти или CPU.

```yaml
version: '3.8'
services:
  bot:
    build: .
    env_file: .env
    depends_on:
      - rabbitmq
      - postgres
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8000/health']
      interval: 30s
      retries: 3

  worker:
    build: .
    env_file: .env
    depends_on:
      - rabbitmq
      - postgres
    deploy:
      replicas: 1

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - '5672:5672'
      - '15672:15672'

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: audio
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - '3000:3000'
```

## 9. Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant B as Bot (aiogram)
    participant Q as Queue (RabbitMQ)
    participant W as Worker Pool
    participant M as Audio Merger
    participant STT as Sber Salute STT (LRO)
    participant LLM as Gigachat LLM
    participant DB as Postgres

    U->>B: Отправляет аудио + режим + /Распознать
    B->>DB: Создаёт запись (Pending)
    B->>U: Запрос принят
    B->>Q: Помещает задачу
    Q->>W: Worker забирает задачу (Running)
    W->>M: Склейка
    W->>STT: STT LRO request
    STT-->>W: Текст
    W->>LLM: LLM запрос
    LLM-->>W: Результат
    W->>DB: Обновляет запись (Finished/Failed)
    W->>Q: Публикует статус
    B->>U: Отправляет Markdown-результат
```

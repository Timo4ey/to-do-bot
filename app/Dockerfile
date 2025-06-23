# === СТАДИЯ 1: Сборка ===
FROM python:3.12.10-alpine as builder

# Установка системных зависимостей
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    musl-dev \
    ffmpeg \
    curl \
    bash \
    libmagic \
    ca-certificates

WORKDIR /app

# Копируем зависимости
COPY pyproject.toml uv.lock ./

# Установка uv и зависимостей
RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache-dir -r pyproject.toml --system

# Добавляем российский корневой сертификат
RUN curl -k "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer" >> $(python -m certifi) && \
    curl -k "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer" -o /usr/local/share/ca-certificates/russiantrustedca.crt && \
    update-ca-certificates

# Удаляем лишнее для чистоты
RUN find /usr/local -depth -name '__pycache__' -exec rm -rf {} + && \
    find /usr/local -name '*.pyc' -delete


# === СТАДИЯ 2: Финальный минимальный образ ===
FROM python:3.12.10-alpine

# Только необходимые runtime-зависимости
RUN apk add --no-cache \
    ffmpeg \
    libmagic \
    ca-certificates \
    bash

WORKDIR /app

# Копируем зависимости, установленные на стадии builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /usr/share/ca-certificates /usr/share/ca-certificates
COPY --from=builder /etc/ssl/certs /etc/ssl/certs

# Копируем само приложение
COPY ./to_do_bot .

# Создаём non-root пользователя
RUN adduser -D appuser && \
    chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]

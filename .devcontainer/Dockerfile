FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install ffmpeg -y

# Установка uv и подготовка проекта
RUN pip install uv

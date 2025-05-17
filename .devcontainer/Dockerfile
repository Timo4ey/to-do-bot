FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install ffmpeg  ca-certificates -y && \
    update-ca-certificates

    
# Установка uv и подготовка проекта
RUN pip install uv certifi


# Установка сертификата минцифры 
RUN curl -k "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer" -w "\n" >> $(python -m certifi)
RUN curl -k "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer" -w "\n" >> /usr/local/share/ca-certificates/russiantrustedca.crt 
RUN update-ca-certificates
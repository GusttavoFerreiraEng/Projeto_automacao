FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 1. Adicionamos python3-dev e build-essential para evitar erros de compilação
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Atualizamos o pip antes de qualquer coisa
RUN pip install --upgrade pip

COPY requirements.txt .

# 3. Instalamos as dependências
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000
FROM python:3.11-slim

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY bot.py .
COPY .env .

# Запуск
CMD ["python", "bot.py"]
import os
import sys
import asyncio
import logging
import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Конфиги
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GAS_WEB_APP_URL = os.environ.get("GAS_WEB_APP_URL")  # URL скрипта Google

# Flask-приложение
app = Flask(__name__)

# Клавиатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"],
    ],
    resize_keyboard=True,
)

# Инициализация Telegram Application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ==== Хендлеры команд ====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:",
        reply_markup=main_keyboard
    )

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get(GAS_WEB_APP_URL)
        data = r.json()
        if "date" in data:
            await update.message.reply_text(f"Текущая дата: {data['date']}\nКакую дату ставим?")
        else:
            await update.message.reply_text(f"Ошибка чтения даты: {data}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

async def set_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    import re
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text):
        try:
            r = requests.post(GAS_WEB_APP_URL, json={"new_date": text})
            data = r.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Новая дата {text} установлена")
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")
    else:
        await update.message.reply_text(
            "Ошибка: неправильный формат даты! Формат должен быть ДД.ММ.ГГГГ"
        )

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True})
        data = r.json()
        if data.get("status") == "ok":
            await update.message.reply_text("Интервалы успешно обновлены!")
        else:
            await update.message.reply_text(f"Ошибка: {data.get('message')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот будет перезапущен...")
    sys.exit(0)

# ==== Роутинг входящих сообщений ====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text in ["/start", "старт"]:
        await start(update, context)
    elif text == "дата":
        await date(update, context)
    elif text == "обновить интервалы":
        await update_intervals(update, context)
    elif text == "рестарт":
        await restart_bot(update, context)
    else:
        await set_new_date(update, context)

# ==== Flask Webhook ====

@app.route("/")
def index():
    return "Bot is running!", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(application.process_update(update))
    return "ok"

# ==== Основной запуск ====

def main():
    # Для Render — включаем только вебхук-режим через Flask, polling не нужен!
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("start", start))
    logger.info("Бот запущен. Ждём события на вебхуке.")
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    main()

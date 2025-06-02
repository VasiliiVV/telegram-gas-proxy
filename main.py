import os
import sys
import logging
import requests
import asyncio
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GAS_WEB_APP_URL = os.environ.get("GAS_WEB_APP_URL")

app = Flask(__name__)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"],
    ],
    resize_keyboard=True,
)

application = Application.builder().token(TELEGRAM_TOKEN).build()

# === HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать! Выбери действие:", reply_markup=main_keyboard)

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
        await update.message.reply_text("Ошибка: неправильный формат даты! Формат должен быть ДД.ММ.ГГГГ")

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

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    loop = asyncio.get_event_loop()
    loop.create_task(application.process_update(update))
    return "ok"

def main():
    # === Хендлеры ===
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("start", start))

    # === Важно: инициализация и запуск PTB ===
    loop = asyncio.get_event_loop()
    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())
    logger.info("Бот запущен. Ждём события на вебхуке.")

    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    main()

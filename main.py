import os
import logging
import requests
from flask import Flask, request

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

TOKEN = os.environ.get('TELEGRAM_TOKEN') or 'ТВОЙ_ТОКЕН'
GAS_URL = os.environ.get('GAS_WEB_APP_URL') or 'ТВОЙ_GAS_URL'

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask-приложение для webhook
app = Flask(__name__)
application = None  # экземпляр Telegram Application

# --- Меню кнопок
main_menu = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Старт"), KeyboardButton("Дата")],
        [KeyboardButton("Обновить Интервалы"), KeyboardButton("Рестарт")],
        [KeyboardButton("Состояние"), KeyboardButton("Обнулить_Vacancies")]
    ], resize_keyboard=True
)

# --- Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:", reply_markup=main_menu
    )

async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(GAS_URL)
        data = resp.json()
        if 'date' in data:
            await update.message.reply_text(f"Текущая дата: {data['date']}")
        else:
            await update.message.reply_text(f"Ошибка: {data.get('message','Нет ответа')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения: {e}")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.post(GAS_URL, json={'update_intervals': True})
        data = resp.json()
        await update.message.reply_text(data.get('message', 'Нет ответа от GAS'))
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения: {e}")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот будет перезапущен…")
    os._exit(0)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(GAS_URL, params={'action': 'status'})
        data = resp.json()
        if 'sum_result' in data and 'last_date_time' in data:
            msg = (
                f"Сумма result: {data['sum_result']}\n"
                f"Последняя дата: {data['last_date_time']}"
            )
        else:
            msg = f"Ошибка: {data.get('message','Нет ответа')}"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения: {e}")

async def reset_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.post(GAS_URL, json={'reset_vacancies': True})
        data = resp.json()
        await update.message.reply_text(data.get('message', 'Нет ответа от GAS'))
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения: {e}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Неизвестная команда. Используй меню ниже.", reply_markup=main_menu
    )

# --- Flask endpoint для Telegram webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.create_task(application.process_update(update))
        return "ok"
    return "not allowed"

# --- Flask endpoint для тестов (GET /)
@app.route("/", methods=["GET"])
def home():
    return "Bot is alive!"

def main():
    global application
    # Telegram-бот: webhook-режим!
    application = Application.builder().token(TOKEN).build()

    # Кнопки и команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^Старт$"), start))
    application.add_handler(MessageHandler(filters.Regex("^Дата$"), date_command))
    application.add_handler(MessageHandler(filters.Regex("^Обновить Интервалы$"), update_intervals))
    application.add_handler(MessageHandler(filters.Regex("^Рестарт$"), restart_command))
    application.add_handler(MessageHandler(filters.Regex("^Состояние$"), status_command))
    application.add_handler(MessageHandler(filters.Regex("^Обнулить_Vacancies$"), reset_vacancies))
    application.add_handler(MessageHandler(filters.ALL, unknown))

    # Настройка webhook
    from telegram import Bot
    bot = Bot(TOKEN)
    webhook_url = os.environ.get('RENDER_EXTERNAL_URL') or f"https://{os.environ.get('RENDER_SERVICE_ID','your-app')}.onrender.com/{TOKEN}"
    bot.delete_webhook()
    bot.set_webhook(webhook_url)

    logging.info("Application started")
    logging.info("Бот запущен. Ждём события на вебхуке.")
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    main()


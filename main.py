import os
import logging
from flask import Flask, request
from telegram import Update, Bot, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# Логи для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
GAS_WEB_APP_URL = os.environ.get("GAS_WEB_APP_URL")

if not TOKEN or not GAS_WEB_APP_URL:
    raise Exception("Отсутствует TELEGRAM_TOKEN или GAS_WEB_APP_URL!")

bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

app = Flask(__name__)

# --- Кнопки ---
keyboard = [
    ["Старт", "Дата"],
    ["Обновить Интервалы", "Рестарт"],
    ["Состояние", "Обнулить_Vacancies"]
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Обработчики команд и текста ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот готов! Используйте кнопки ниже.",
        reply_markup=markup
    )

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Твой вызов GAS по API и возврат даты
    await update.message.reply_text("Текущая дата: ...")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Твой вызов GAS по API
    await update.message.reply_text("Интервалы обновлены.")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот перезапущен.")

async def state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Вызов GAS по API и ответ
    await update.message.reply_text("Статус: ...")

async def obnulit_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Вызов GAS по API для обнуления
    await update.message.reply_text("Вакансии обнулены.")

# --- Подключаем обработчики ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("date", date))
application.add_handler(CommandHandler("update_intervals", update_intervals))
application.add_handler(CommandHandler("restart", restart))
application.add_handler(CommandHandler("state", state))
application.add_handler(CommandHandler("obnulit_vacancies", obnulit_vacancies))

# --- Обработка текстовых команд (кнопок) ---
from telegram.ext import MessageHandler, filters

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "старт":
        await start(update, context)
    elif text == "дата":
        await date(update, context)
    elif text == "обновить интервалы":
        await update_intervals(update, context)
    elif text == "рестарт":
        await restart(update, context)
    elif text == "состояние":
        await state(update, context)
    elif text == "обнулить_vacancies":
        await obnulit_vacancies(update, context)
    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=markup)

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# --- Flask endpoint ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.create_task(application.process_update(update))
    return "ok"

# --- Установка вебхука при старте ---
@app.before_first_request
def set_webhook():
    webhook_url = f"{os.getenv('RENDER_EXTERNAL_URL', '').rstrip('/')}/{TOKEN}"
    if webhook_url:
        bot.delete_webhook()
        bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")

if __name__ == "__main__":
    app.run(port=10000)


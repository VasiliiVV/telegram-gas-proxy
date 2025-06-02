import os
import logging
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Конфиги
TOKEN = os.getenv("TOKEN")  # обязательно только так!
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # подставь свой chat_id

# Инициализация логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Telegram
application = Application.builder().token(TOKEN).build()

# ========== HANDLERS ==========

# Главное меню
MAIN_MENU = [
    ["Обновить интервалы", "Состояние"],
    ["Установить дату", "Обнулить_Vacancies"]
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    )

# Пример других команд, здесь только каркас! Допиши свои функции!
async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Тут логика обновления через Google Apps Script
    await update.message.reply_text("Интервалы обновлены.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Тут логика получения статуса через GAS
    await update.message.reply_text("Сумма result: ...\nПоследняя дата: ...")

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите дату в формате ДД.ММ.ГГГГ")

async def reset_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Тут логика очистки таблицы через GAS
    await update.message.reply_text("Вакансии очищены!")

# Dispatcher
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Regex("^Обновить интервалы$"), update_intervals))
application.add_handler(MessageHandler(filters.Regex("^Состояние$"), status))
application.add_handler(MessageHandler(filters.Regex("^Установить дату$"), set_date))
application.add_handler(MessageHandler(filters.Regex("^Обнулить_Vacancies$"), reset_vacancies))
application.add_handler(MessageHandler(filters.ALL, start))  # На все остальное — главное меню

# ========== FLASK WEBHOOK ==========
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

@app.route("/", methods=["GET", "HEAD"])
def index():
    return "ok"

if __name__ == "__main__":
    # Важно: только так ставим webhook!
    WEBHOOK_BASE = os.getenv("WEBHOOK_BASE")
    if not WEBHOOK_BASE:
        raise Exception("WEBHOOK_BASE не указан!")
    url = f"{WEBHOOK_BASE}/{TOKEN}"
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        webhook_url=url,
        allowed_updates=Update.ALL_TYPES
    )

import os
import logging
import requests
import asyncio
from flask import Flask, request
from telegram import (
    Bot, Update, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# --- Настройки ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "ТВОЙ_ТОКЕН"
GAS_URL = os.getenv("GAS_URL") or "ТВОЙ_GAS_УРЛ"
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID") or "ТВОЙ_ID")  # только твой id

# --- Логирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask app & PTB ---
app = Flask(__name__)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# --- Клавиатура ---
main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton('Старт'), KeyboardButton('Дата')],
    [KeyboardButton('Обновить Интервалы'), KeyboardButton('Состояние')],
    [KeyboardButton('Обнулить_Vacancies'), KeyboardButton('Рестарт')],
], resize_keyboard=True)

# --- Фильтр только для тебя ---
def is_admin(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.id == ADMIN_CHAT_ID

# --- Хендлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "Привет! Я бот для управления Google Таблицей.", reply_markup=main_keyboard
    )

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        r = requests.get(GAS_URL)
        data = r.json()
        await update.message.reply_text(
            f"Текущая дата: {data.get('date', 'нет данных')}", reply_markup=main_keyboard
        )
    except Exception as ex:
        await update.message.reply_text(f"Ошибка: {ex}")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        r = requests.post(GAS_URL, json={"update_intervals": True})
        data = r.json()
        await update.message.reply_text(
            data.get("message", "Ошибка обновления"), reply_markup=main_keyboard
        )
    except Exception as ex:
        await update.message.reply_text(f"Ошибка: {ex}")

async def state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        r = requests.post(GAS_URL, json={"status": True})
        data = r.json()
        result_sum = data.get("result_sum", "нет данных")
        last_date = data.get("last_date", "нет данных")
        await update.message.reply_text(
            f"Сумма result: {result_sum}\nПоследняя дата: {last_date}",
            reply_markup=main_keyboard
        )
    except Exception as ex:
        await update.message.reply_text(f"Ошибка: {ex}")

async def clear_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        r = requests.post(GAS_URL, json={"clear_vacancies": True})
        data = r.json()
        await update.message.reply_text(
            data.get("message", "Не удалось обнулить"), reply_markup=main_keyboard
        )
    except Exception as ex:
        await update.message.reply_text(f"Ошибка: {ex}")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text("Рестартую (перезапусти сервис вручную на Render)", reply_markup=main_keyboard)

# --- Кнопки/текстовые команды ---
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    txt = update.message.text.strip().lower()
    if txt == "старт":
        await start(update, context)
    elif txt == "дата":
        await date(update, context)
    elif txt == "обновить интервалы":
        await update_intervals(update, context)
    elif txt == "состояние":
        await state(update, context)
    elif txt == "обнулить_vacancies":
        await clear_vacancies(update, context)
    elif txt == "рестарт":
        await restart(update, context)
    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=main_keyboard)

# --- Роутинг PTB ---
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_router))
application.add_handler(CommandHandler("start", start))

# --- Webhook для Telegram ---
@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(application.process_update(update))
    return "ok"

@app.route("/", methods=["GET"])
def root():
    return "Бот работает!"

# --- Запуск Flask ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

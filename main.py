import os
import logging
from flask import Flask, request, abort
import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === КОНФИГ ===
TOKEN = os.getenv('TELEGRAM_TOKEN')
GAS_WEB_APP_URL = os.getenv('GAS_WEB_APP_URL')
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # если нет — 0
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'your-app-name.onrender.com')}/{TOKEN}"

# === ЛОГГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === FLASK APP ===
app = Flask(__name__)

# === TELEGRAM BOT ===
application = Application.builder().token(TOKEN).build()

# === КНОПКИ ===
MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Старт"), KeyboardButton("Дата")],
        [KeyboardButton("Обновить Интервалы"), KeyboardButton("Рестарт")],
        [KeyboardButton("Состояние")],
        [KeyboardButton("Обнулить_Vacancies")],
    ],
    resize_keyboard=True
)

# === ХЭНДЛЕРЫ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать!", reply_markup=MAIN_MENU)

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(GAS_WEB_APP_URL)
        data = resp.json()
        await update.message.reply_text(f"Текущая дата: {data.get('date', 'Ошибка!')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении даты: {e}")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True})
        data = resp.json()
        await update.message.reply_text(data.get("message", "Готово!"))
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обновлении: {e}")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот будет перезапущен…")
    os._exit(0)  # Render сам рестартанет сервис

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"status": True})
        data = resp.json()
        msg = data.get("message", "Нет данных!")
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении статуса: {e}")

async def reset_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Нет прав.")
        return
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"reset_vacancies": True})
        data = resp.json()
        await update.message.reply_text(data.get("message", "Таблица очищена!"))
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка команд через текстовые кнопки
    txt = update.message.text.lower()
    if txt == "старт":
        await start(update, context)
    elif txt == "дата":
        await date(update, context)
    elif txt == "обновить интервалы":
        await update_intervals(update, context)
    elif txt == "рестарт":
        await restart(update, context)
    elif txt == "состояние":
        await status(update, context)
    elif txt == "обнулить_vacancies":
        await reset_vacancies(update, context)
    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=MAIN_MENU)

# === ПРИВЯЗКА ХЭНДЛЕРОВ ===
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo_handler))

# === WEBHOOK ОБРАБОТЧИК ===
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return "ok"
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        abort(500)

# === ПРИЛОЖЕНИЕ ЗАПУСК ===
def setup_webhook():
    from telegram import Bot
    bot = application.bot
    bot.delete_webhook()
    bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    setup_webhook()
    logger.info("Бот запущен. Ждём события на вебхуке.")
    app.run(host="0.0.0.0", port=10000)


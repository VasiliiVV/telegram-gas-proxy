import os
import logging
import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- Конфиг из env ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
GAS_WEB_APP_URL = os.getenv("GAS_WEB_APP_URL")  # url твоего GAS-скрипта
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/{TOKEN}"

# --- Логирование ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Flask ---
app = Flask(__name__)

# --- Telegram Application ---
application = Application.builder().token(TOKEN).build()

# --- Клавиатура ---
keyboard = [
    [KeyboardButton("Старт"), KeyboardButton("Дата")],
    [KeyboardButton("Обновить Интервалы"), KeyboardButton("Рестарт")],
    [KeyboardButton("Состояние"), KeyboardButton("Обнулить Вакансии")],
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Основные Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот готов к работе!", reply_markup=reply_markup)

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get(GAS_WEB_APP_URL)
    try:
        data = resp.json()
        await update.message.reply_text(f"Текущая дата: {data['date']}", reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text("Ошибка получения даты.", reply_markup=reply_markup)

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True})
    try:
        data = resp.json()
        msg = data.get('message', 'Интервалы обновлены.')
        await update.message.reply_text(msg, reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text("Ошибка обновления интервалов.", reply_markup=reply_markup)

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот будет перезапущен…", reply_markup=reply_markup)
    os._exit(0)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.post(GAS_WEB_APP_URL, json={"status_request": True})
    try:
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text(
                f"Сумма result: {data['result_sum']}\nПоследняя дата: {data['last_date']}", 
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("Ошибка получения состояния.", reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text("Ошибка связи с Google Sheets.", reply_markup=reply_markup)

async def reset_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.post(GAS_WEB_APP_URL, json={"reset_vacancies": True})
    try:
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text(data.get("message", "Таблица Intervals обнулена."), reply_markup=reply_markup)
        else:
            await update.message.reply_text("Ошибка при обнулении таблицы.", reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text("Ошибка связи с Google Sheets.", reply_markup=reply_markup)

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Проверяем на формат даты (ДД.ММ.ГГГГ)
    import re
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', text):
        resp = requests.post(GAS_WEB_APP_URL, json={"new_date": text})
        try:
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Новая дата {text} установлена", reply_markup=reply_markup)
            else:
                await update.message.reply_text(data.get("message", "Ошибка установки даты."), reply_markup=reply_markup)
        except Exception:
            await update.message.reply_text("Ошибка связи с Google Sheets.", reply_markup=reply_markup)

# --- Обработчик всех текстовых сообщений ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
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
    elif txt == "обнулить вакансии":
        await reset_vacancies(update, context)
    else:
        # Попробуем обработать как установку даты
        await set_date(update, context)

# --- Регистрация Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# --- Flask endpoint (webhook) ---
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK"

# --- healthcheck ---
@app.route("/", methods=["GET"])
def healthcheck():
    return "Bot is running!"

if __name__ == "__main__":
    # Устанавливаем webhook (асинхронно не ждем)
    from telegram import Bot
    bot = Bot(token=TOKEN)
    try:
        import asyncio
        asyncio.get_event_loop().run_until_complete(bot.delete_webhook())
        asyncio.get_event_loop().run_until_complete(bot.set_webhook(WEBHOOK_URL))
    except Exception as e:
        logging.warning(f"Ошибка установки webhook: {e}")
    logging.info("Бот запущен. Ждём события на вебхуке.")
    app.run(host="0.0.0.0", port=10000)

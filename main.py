import os
import sys
import logging
import requests
import asyncio
import signal
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GAS_WEB_APP_URL = os.environ.get("GAS_WEB_APP_URL")

if not TELEGRAM_TOKEN or not GAS_WEB_APP_URL:
    logger.error("No TELEGRAM_TOKEN or GAS_WEB_APP_URL in env!")
    sys.exit(1)

app = Flask(__name__)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"]
    ],
    resize_keyboard=True,
)

# === PTB Application ===
application = Application.builder().token(TELEGRAM_TOKEN).build()
ptb_loop = None

# === HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать! Выбери действие:", reply_markup=main_keyboard)

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(GAS_WEB_APP_URL, timeout=10)
        data = resp.json()
        if "date" in data:
            await update.message.reply_text(f"Текущая дата: {data['date']}\nКакую дату ставим?")
        else:
            await update.message.reply_text(f"Ошибка чтения даты: {data}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {str(e)}")

async def set_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    import re
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text):
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"new_date": text}, timeout=10)
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Новая дата {text} установлена")
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка соединения с таблицей: {str(e)}")
    else:
        await update.message.reply_text("Ошибка: неправильный формат даты! Формат должен быть ДД.ММ.ГГГГ")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True}, timeout=15)
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text("Интервалы успешно обновлены!")
        else:
            await update.message.reply_text(f"Ошибка: {data.get('message')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {str(e)}")

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
    # Гарантировано thread-safe запуск в PTB loop:
    fut = asyncio.run_coroutine_threadsafe(application.process_update(update), ptb_loop)
    try:
        fut.result(timeout=30)  # ждем окончания обработки, можно убрать
    except Exception as ex:
        logger.error(f"PTB обработка update завершилась с ошибкой: {ex}")
    return "ok"

def handle_exit(*args):
    logger.info("SIGTERM/SIGINT: корректно завершаем PTB loop...")
    if ptb_loop and ptb_loop.is_running():
        ptb_loop.call_soon_threadsafe(ptb_loop.stop)
    sys.exit(0)

def main():
    global ptb_loop
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("start", start))
    # Сохраняем loop, стартуем в нем PTB, затем Flask в основном потоке
    ptb_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ptb_loop)
    ptb_loop.run_until_complete(application.initialize())
    ptb_loop.run_until_complete(application.start())
    logger.info("Бот запущен. Ждём события на вебхуке.")

    # Корректный shutdown
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    # Открываем webhook
    from telegram.constants import ParseMode
    url = f"{os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')}/{TELEGRAM_TOKEN}"
    if url:
        ptb_loop.run_until_complete(application.bot.delete_webhook())
        ptb_loop.run_until_complete(application.bot.set_webhook(url, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True))
        logger.info(f"Webhook set to: {url}")

    # Запускаем Flask на 0.0.0.0:10000 (или другой порт, если задан)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()

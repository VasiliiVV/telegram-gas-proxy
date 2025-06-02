import os
import logging
import requests
from flask import Flask, request
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import asyncio

# Логирование
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
GAS_WEB_APP_URL = os.getenv("GAS_WEB_APP_URL")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TOKEN or not GAS_WEB_APP_URL or not ADMIN_CHAT_ID:
    logger.critical("Ошибка: Проверьте TELEGRAM_TOKEN, GAS_WEB_APP_URL и ADMIN_CHAT_ID в переменных окружения")
    raise Exception("Нет критичной переменной окружения!")

ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)

# Flask app
app = Flask(__name__)

# === Кнопки меню ===
keyboard = [
    [KeyboardButton("Старт"), KeyboardButton("Дата")],
    [KeyboardButton("Обновить Интервалы"), KeyboardButton("Рестарт")],
    [KeyboardButton("Состояние"), KeyboardButton("Обнулить Вакансии")]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Telegram application ===
application = Application.builder().token(TOKEN).build()

# === Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выберите действие:", reply_markup=reply_markup
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    chat_id = update.effective_chat.id

    # === Обработка кнопок ===
    if text in ["старт", "/start"]:
        await start(update, context)
        return

    elif text == "дата":
        try:
            resp = requests.get(f"{GAS_WEB_APP_URL}?action=get_date", timeout=10)
            data = resp.json()
            if data.get("date"):
                await update.message.reply_text(f"Текущая дата: {data['date']}", reply_markup=reply_markup)
            else:
                raise Exception(data.get("message", "Неизвестная ошибка"))
        except Exception as e:
            await update.message.reply_text(f"Ошибка получения даты: {e}", reply_markup=reply_markup)

    elif text == "обновить интервалы":
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True}, timeout=20)
            data = resp.json()
            msg = data.get("message", "Интервалы успешно обновлены!")
            await update.message.reply_text(msg, reply_markup=reply_markup)
        except Exception as e:
            await update.message.reply_text(f"Ошибка обновления интервалов: {e}", reply_markup=reply_markup)

    elif text == "рестарт":
        await update.message.reply_text("Бот успешно перезапущен! (На Render фактически не рестартует контейнер, но кнопку поддерживаем)", reply_markup=reply_markup)

    elif text == "состояние":
        try:
            resp = requests.get(f"{GAS_WEB_APP_URL}?action=status", timeout=20)
            data = resp.json()
            result = data.get("result", "Нет данных")
            last_date = data.get("last_date", "Нет даты")
            await update.message.reply_text(
                f"Сумма result: {result}\nПоследняя дата: {last_date}",
                reply_markup=reply_markup
            )
        except Exception as e:
            await update.message.reply_text(f"Ошибка получения состояния: {e}", reply_markup=reply_markup)

    elif text == "обнулить вакансии":
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"clear_vacancies": True}, timeout=20)
            data = resp.json()
            msg = data.get("message", "Данные по Vacancies успешно обнулены!")
            await update.message.reply_text(msg, reply_markup=reply_markup)
        except Exception as e:
            await update.message.reply_text(f"Ошибка обнуления: {e}", reply_markup=reply_markup)

    else:
        await update.message.reply_text(
            "Неизвестная команда. Используйте кнопки меню.", reply_markup=reply_markup
        )

# === Flask Webhook endpoint ===
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
        return "ok"
    except Exception as e:
        logger.error(f"Ошибка в обработке вебхука: {e}")
        return "error", 500

@app.route("/", methods=["GET"])
def index():
    return "Bot is alive!", 200

# === Main ===
def main():
    # Устанавливаем webhook
    webhook_url = f"{os.getenv('WEBHOOK_BASE', '')}/{TOKEN}"
    # Обновление вебхука (с await, если бот поддерживает)
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
        loop.run_until_complete(application.bot.set_webhook(webhook_url))
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {e}")

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    # Запуск Flask
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    main()

import os
import logging
import asyncio

from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
)

# --- Настройки ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Render env var
GAS_WEB_APP_URL = os.getenv("GAS_WEB_APP_URL")  # Render env var

# --- Flask ---
app = Flask(__name__)

# --- Telegram Application ---
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# --- Клавиатура ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"],
    ],
    resize_keyboard=True,
)

# --- Команды ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:",
        reply_markup=main_keyboard,
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    if text == "старт":
        await start(update, context)
    elif text == "дата":
        # Получить дату из google-таблицы
        import requests
        try:
            resp = requests.get(GAS_WEB_APP_URL)
            data = resp.json()
            if data.get("date"):
                await update.message.reply_text(
                    f"Текущая дата: {data['date']}\nКакую дату ставим?",
                    reply_markup=main_keyboard,
                )
                context.user_data["waiting_for_date"] = True
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

    elif text == "обновить интервалы":
        import requests
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True})
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text("Интервалы успешно обновлены!", reply_markup=main_keyboard)
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

    elif text == "рестарт":
        await update.message.reply_text("Бот будет перезапущен...", reply_markup=main_keyboard)
        await context.application.stop()
        # Render сам перезапустит контейнер через healthcheck

    else:
        # Если ожидается дата
        if context.user_data.get("waiting_for_date"):
            import re, requests
            date_pattern = r"^([0-2][0-9]|3[0-1])\.(0[1-9]|1[0-2])\.(\d{4})$"
            if re.match(date_pattern, text):
                try:
                    resp = requests.post(GAS_WEB_APP_URL, json={"new_date": text})
                    data = resp.json()
                    if data.get("status") == "ok":
                        await update.message.reply_text(
                            f"Новая дата {data['date']} установлена",
                            reply_markup=main_keyboard,
                        )
                        context.user_data["waiting_for_date"] = False
                    else:
                        await update.message.reply_text(f"Ошибка: {data.get('message')}")
                except Exception as e:
                    await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")
            else:
                await update.message.reply_text(
                    "Ошибка: неправильный формат даты. Формат должен быть ДД.ММ.ГГГГ"
                )
        else:
            await update.message.reply_text(
                "Выбери действие на клавиатуре.", reply_markup=main_keyboard
            )

# --- Telegram handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Flask endpoint for Telegram webhook ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))
    return "ok"

# --- Установка webhook ---
async def setup_webhook():
    await application.bot.delete_webhook()
    webhook_url = f"https://telegram-gas-proxy-g0f8.onrender.com/{TELEGRAM_TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    print(f"Webhook set to: {webhook_url}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(setup_webhook())
    # Старт Flask-сервера (Render ожидает app.run(...))
    app.run(host="0.0.0.0", port=10000)

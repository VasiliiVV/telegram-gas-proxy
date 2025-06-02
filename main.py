import os
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- Конфигурация ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = "/" + 7887190973:AAH1-3zcBhs97R8eymQbay8f8iV6Xfs1yus # например: /7887190973:AAH.../
WEBHOOK_PORT = int(os.getenv("PORT", 10000))
GAS_WEB_APP_URL = os.getenv("GAS_WEB_APP_URL")

app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

# --- Клавиатура ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"]
    ],
    resize_keyboard=True
)

# --- Обработка команд и кнопок ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:",
        reply_markup=main_keyboard
    )

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import requests
    try:
        r = requests.get(GAS_WEB_APP_URL)
        data = r.json()
        if "date" in data:
            await update.message.reply_text(f"Текущая дата: {data['date']}\nКакую дату ставим?")
            context.user_data['awaiting_new_date'] = True
        else:
            await update.message.reply_text("Ошибка: не удалось получить дату.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()

    if context.user_data.get('awaiting_new_date'):
        import requests
        try:
            r = requests.post(GAS_WEB_APP_URL, json={"new_date": msg})
            data = r.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Новая дата {msg} установлена")
            else:
                await update.message.reply_text(data.get("message", "Ошибка!"))
        except Exception as e:
            await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")
        context.user_data['awaiting_new_date'] = False
        return

    # Кнопки меню
    if msg == "Старт":
        await start(update, context)
    elif msg == "Дата":
        await date(update, context)
    elif msg == "Обновить Интервалы":
        import requests
        try:
            r = requests.post(GAS_WEB_APP_URL, json={"update_intervals": True})
            data = r.json()
            if data.get("status") == "ok":
                await update.message.reply_text("Интервалы успешно обновлены!")
            else:
                await update.message.reply_text(data.get("message", "Ошибка обновления!"))
        except Exception as e:
            await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")
    elif msg == "Рестарт":
        await update.message.reply_text("Бот будет перезапущен...")
        import sys
        sys.exit(0)
    else:
        await update.message.reply_text("Выбери действие на клавиатуре.", reply_markup=main_keyboard)

# --- Интеграция с Telegram (через Application) ---
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CommandHandler("start", start))

# --- Flask endpoint для Telegram webhook ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put(update)
    return "ok", 200

@app.route("/", methods=["GET"])
def health():
    return "Bot is running!", 200

# --- Установка webhook и запуск сервера ---
if __name__ == "__main__":
    # Установка webhook на адрес Render (host/PORT/TELEGRAM_TOKEN)
    external_url = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    webhook_url = f"https://{external_url}{WEBHOOK_PATH}"
    bot.delete_webhook()
    bot.set_webhook(webhook_url)
    print(f"Webhook set to: {webhook_url}")

    # Запуск Flask-сервера
    app.run(host="0.0.0.0", port=WEBHOOK_PORT)

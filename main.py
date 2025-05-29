import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GAS_WEB_APP_URL = os.getenv('GAS_WEB_APP_URL')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    user_data = context.user_data

    # Если бот ждет новую дату
    if user_data.get("waiting_for_date"):
        new_date = update.message.text.strip()
        # Отправим дату на GAS
        resp = requests.post(GAS_WEB_APP_URL, json={'new_date': new_date})
        if resp.ok and resp.json().get("status") == "ok":
            await update.message.reply_text(f"Новая дата {new_date} установлена")
        else:
            await update.message.reply_text("Ошибка при установке даты!")
        user_data["waiting_for_date"] = False
        return

    # Если пользователь пишет "дата"
    if text == "дата":
        # Получим текущую дату через GET
        resp = requests.get(GAS_WEB_APP_URL)
        if resp.ok:
            date = resp.json().get("date", "не указана")
            await update.message.reply_text(f"Текущая дата: {date}\nКакую дату ставим?")
            user_data["waiting_for_date"] = True
        else:
            await update.message.reply_text("Ошибка при получении даты!")
        return

    # Для всех остальных сообщений - стандартный ответ
    await update.message.reply_text("Напиши 'Дата', чтобы узнать и поменять дату.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()

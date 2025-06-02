import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# --- НАСТРОЙКИ ---
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
GAS_WEB_APP_URL = os.environ.get("GAS_WEB_APP_URL")
ALLOWED_CHAT_ID = os.environ.get("ALLOWED_CHAT_ID")  # можно без этой проверки, если только ты пользуешься

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- КЛАВИАТУРА ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"]
    ],
    resize_keyboard=True
)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Если ты хочешь ограничить только своим ID:
    # if str(chat_id) != str(ALLOWED_CHAT_ID):
    #     await update.message.reply_text("Нет доступа.", reply_markup=main_keyboard)
    #     return

    if text == "Старт":
        await update.message.reply_text(
            "Добро пожаловать! Выбери действие:", reply_markup=main_keyboard
        )
    elif text == "Дата":
        try:
            r = requests.get(GAS_WEB_APP_URL, timeout=10)
            data = r.json()
            if "date" in data:
                await update.message.reply_text(
                    f"Текущая дата: {data['date']}\nКакую дату ставим?",
                    reply_markup=main_keyboard
                )
            else:
                await update.message.reply_text(
                    f"Ошибка: {data.get('message', 'Нет данных!')}", reply_markup=main_keyboard
                )
        except Exception as e:
            await update.message.reply_text(
                f"Ошибка соединения с таблицей: {e}", reply_markup=main_keyboard
            )

    elif is_valid_date(text):
        # Если введённая строка — дата ДД.ММ.ГГГГ
        try:
            resp = requests.post(
                GAS_WEB_APP_URL,
                json={"new_date": text},
                timeout=10
            )
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(
                    f"Новая дата {text} установлена", reply_markup=main_keyboard
                )
            else:
                await update.message.reply_text(
                    f"Ошибка: {data.get('message', 'Не удалось обновить дату!')}", reply_markup=main_keyboard
                )
        except Exception as e:
            await update.message.reply_text(
                f"Ошибка соединения с таблицей: {e}", reply_markup=main_keyboard
            )

    elif text == "Обновить Интервалы":
        try:
            resp = requests.post(
                GAS_WEB_APP_URL,
                json={"update_intervals": True},
                timeout=15
            )
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(
                    "Интервалы успешно обновлены!", reply_markup=main_keyboard
                )
            else:
                await update.message.reply_text(
                    f"Ошибка: {data.get('message', 'Не удалось обновить интервалы!')}", reply_markup=main_keyboard
                )
        except Exception as e:
            await update.message.reply_text(
                f"Ошибка соединения с таблицей: {e}", reply_markup=main_keyboard
            )

    elif text == "Рестарт":
        await update.message.reply_text("Бот будет перезапущен...", reply_markup=main_keyboard)
        # Корректный способ рестарта на Render — завершить процесс
        import sys
        sys.exit(0)

    else:
        await update.message.reply_text(
            "Выбери действие на клавиатуре.", reply_markup=main_keyboard
        )

# --- ПРОВЕРКА ДАТЫ ---
def is_valid_date(text):
    import re
    return re.match(r"^([0-2][0-9]|3[0-1])\.(0[1-9]|1[0-2])\.(\d{4})$", text) is not None

# --- ОСНОВНОЙ ЗАПУСК ---
def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен. Ожидаю сообщения в Telegram...")
    application.run_polling()

if __name__ == "__main__":
    main()

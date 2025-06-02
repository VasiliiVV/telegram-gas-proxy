import os
import logging
import requests
import sys
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GAS_WEB_APP_URL = os.getenv('GAS_WEB_APP_URL')

# Только твой user_id!
RESTART_ALLOWED_USER_IDS = [1411866927]

# Клавиатура: 2 строки — 4 кнопки
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Дата"],
        ["Обновить Интервалы", "Рестарт"]
    ],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:",
        reply_markup=main_keyboard
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in RESTART_ALLOWED_USER_IDS:
        await update.message.reply_text("Нет прав на рестарт.", reply_markup=main_keyboard)
        return
    await update.message.reply_text("Бот будет перезапущен через 3 секунды...", reply_markup=main_keyboard)
    await context.application.shutdown()
    await context.application.stop()
    os._exit(0)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_data = context.user_data

    # --- Кнопка "Рестарт" ---
    if text.lower() == "рестарт":
        user_id = update.effective_user.id
        if user_id not in RESTART_ALLOWED_USER_IDS:
            await update.message.reply_text("Нет прав на рестарт.", reply_markup=main_keyboard)
            return
        await update.message.reply_text("Бот будет перезапущен через 3 секунды...", reply_markup=main_keyboard)
        await context.application.shutdown()
        await context.application.stop()
        os._exit(0)
        return

    # --- Кнопка "Обновить Интервалы" ---
    if text.lower() == "обновить интервалы":
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={'update_intervals': True}, timeout=15)
            if resp.ok:
                res_json = resp.json()
                if res_json.get("status") == "ok":
                    await update.message.reply_text(
                        "Интервалы успешно обновлены!",
                        reply_markup=main_keyboard
                    )
                else:
                    await update.message.reply_text(
                        f"Ошибка при обновлении интервалов: {res_json.get('message', 'неизвестная ошибка')}",
                        reply_markup=main_keyboard
                    )
            else:
                await update.message.reply_text(
                    f"Ошибка HTTP {resp.status_code} при обновлении интервалов.",
                    reply_markup=main_keyboard
                )
        except Exception as ex:
            await update.message.reply_text(
                f"Ошибка соединения: {ex}",
                reply_markup=main_keyboard
            )
        return

    # --- Кнопка "Старт" ---
    if text.lower() == "старт":
        await update.message.reply_text(
            "Бот готов к работе. Доступные функции:\n- Дата\n- Обновить Интервалы\n- Рестарт\n- Старт",
            reply_markup=main_keyboard
        )
        user_data["waiting_for_date"] = False
        return

    # --- Ожидание ввода новой даты ---
    if user_data.get("waiting_for_date"):
        new_date = text.strip()
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={'new_date': new_date}, timeout=10)
            if resp.ok:
                res_json = resp.json()
                if res_json.get("status") == "ok":
                    await update.message.reply_text(
                        f"Новая дата {new_date} установлена",
                        reply_markup=main_keyboard
                    )
                elif res_json.get("status") == "error" and "формат" in res_json.get("message", "").lower():
                    await update.message.reply_text(
                        "Ошибка: неправильный формат даты! Формат должен быть ДД.ММ.ГГГГ",
                        reply_markup=main_keyboard
                    )
                else:
                    await update.message.reply_text(
                        f"Ошибка при установке даты! Ответ: {res_json}",
                        reply_markup=main_keyboard
                    )
            else:
                await update.message.reply_text(
                    f"Ошибка при установке даты! (HTTP {resp.status_code})",
                    reply_markup=main_keyboard
                )
        except Exception as ex:
            await update.message.reply_text(
                f"Ошибка соединения с таблицей: {ex}",
                reply_markup=main_keyboard
            )
        user_data["waiting_for_date"] = False
        return

    # --- Кнопка "Дата" ---
    if text.lower() == "дата":
        try:
            resp = requests.get(GAS_WEB_APP_URL, timeout=10)
            if resp.ok:
                date = resp.json().get("date", "не указана")
                await update.message.reply_text(
                    f"Текущая дата: {date}\nКакую дату ставим?",
                    reply_markup=main_keyboard
                )
                user_data["waiting_for_date"] = True
            else:
                await update.message.reply_text("Ошибка при получении даты!", reply_markup=main_keyboard)
        except Exception as ex:
            await update.message.reply_text(
                f"Ошибка соединения с таблицей: {ex}",
                reply_markup=main_keyboard
            )
        return

    # --- Любое другое сообщение ---
    await update.message.reply_text(
        "Выбери действие на клавиатуре.",
        reply_markup=main_keyboard
    )

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()

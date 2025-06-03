import os
import sys
import logging
import asyncio
import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import threading
import traceback


# === Logging ===
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ENV ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GAS_WEB_APP_URL = os.getenv("GAS_WEB_APP_URL")

if not TELEGRAM_TOKEN or not GAS_WEB_APP_URL:
    logger.error("Set TELEGRAM_TOKEN and GAS_WEB_APP_URL in environment!")
    sys.exit(1)

# === Spreadsheet IDs ===
SPREADSHEET_IDS = {
    "5": "1pRomG_o3T4a6N0ASPq-zlrIv_0hQ7EODZYmdU0iz33U",
    "4": "1wdmm4o5Q6j9HCYD18BTpruUqJK8ErL7F4WI1KwupE7E",
    "3": "1czq9G66AwmUTeT1lcqCNfZAweF2FwIEa91fAaiOKGp8",
    "2": "1sJnM4Rc9eBqINgy-yFRGLBiv3y6R9Sh-aI_uQ9L7ItI",
}
USER_CURRENT_SHEET = {}  # user_id: spreadsheet_id

# === Flask ===
app = Flask(__name__)

# === PTB Application & Loop ===
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
ptb_loop = asyncio.new_event_loop()

# === Клавиатура ===
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Старт", "Рестарт"],
        ["Выбрать файл 2", "Выбрать файл 3"],
        ["Выбрать файл 4", "Выбрать файл 5"],
        ["Дата", "Обновить Интервалы"],
        ["Состояние", "Сохранить по дате"],
        ["Очистить vacancies"]
    ],
    resize_keyboard=True
)

# === Хендлеры ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:", reply_markup=main_keyboard
    )

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    sheet_id = USER_CURRENT_SHEET.get(user_id)
    if not sheet_id:
        await update.message.reply_text("Сначала выберите файл (кнопка ниже).")
        return
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id}, timeout=15)
        data = resp.json()
        if data.get("date"):
            await update.message.reply_text(f"Текущая дата: {data['date']}\nКакую дату ставим?")
        else:
            await update.message.reply_text(f"Ошибка GAS: {data}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    sheet_id = USER_CURRENT_SHEET.get(user_id)
    if not sheet_id:
        await update.message.reply_text("Сначала выберите файл (кнопка ниже).")
        return
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "update_intervals": True}, timeout=30)
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text("Интервалы успешно обновлены!")
        else:
            await update.message.reply_text(f"Ошибка обновления: {data.get('message', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка GAS: {e}")

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    await update.message.reply_text("Бот будет перезапущен...")
    await context.application.stop()
    sys.exit(0)

async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    sheet_id = USER_CURRENT_SHEET.get(user_id)
    if not sheet_id:
        await update.message.reply_text("Сначала выберите файл (кнопка ниже).")
        return
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "action": "status"}, timeout=30)
        data = resp.json()
        # Запрашиваем дату обработки отдельно
        resp_date = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id}, timeout=15)
        date_data = resp_date.json()
        process_date = date_data.get("date", "-")

        sum_result = data.get("sum_result")
        last_date_time = data.get("last_date_time")
        total = data.get("total_intervals")
        processed = data.get("processed_intervals")
        msg = (
            f"Дата обработки: {process_date}\n"
            f"Сумма result: {sum_result}\n"
            f"Последняя дата: {last_date_time}\n"
            f"Всего интервалов: {total}\n"
            f"Обработано: {processed}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении состояния: {e}")

async def set_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    sheet_id = USER_CURRENT_SHEET.get(user_id)
    if not update.message or not update.message.text or not sheet_id:
        await update.message.reply_text("Сначала выберите файл (кнопка ниже).")
        return
    new_date = update.message.text.strip()
    import re
    if re.match(r"^([0-2][0-9]|3[0-1])\.(0[1-9]|1[0-2])\.(\d{4})$", new_date):
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "new_date": new_date}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Новая дата {new_date} установлена")
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message', 'Неизвестная ошибка')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при установке даты: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.message.from_user.id

    # === Проверка доступа ===
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    text = update.message.text.strip().lower()

    # === Выбор файла ===
    if text.startswith("выбрать файл"):
        num = text.split()[-1]
        if num in SPREADSHEET_IDS:
            USER_CURRENT_SHEET[user_id] = SPREADSHEET_IDS[num]
            await update.message.reply_text(f"Выбран файл №{num}")
        else:
            await update.message.reply_text("Такого файла нет!")
        return

    if text in ["/start", "старт"]:
        await start(update, context)
    elif text == "дата":
        await date(update, context)
    elif text == "обновить интервалы":
        await update_intervals(update, context)
    elif text == "рестарт":
        await restart_bot(update, context)
    elif text == "состояние":
        await get_status(update, context)
    elif text == "очистить vacancies":
        sheet_id = USER_CURRENT_SHEET.get(user_id)
        if not sheet_id:
            await update.message.reply_text("Сначала выберите файл (кнопка ниже).")
            return
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "clear_vacancies": True}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text("Лист Vacancies успешно очищен!")
            else:
                await update.message.reply_text(f"Ошибка очистки: {data.get('message', 'Неизвестная ошибка')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка GAS: {e}")
    elif text == "сохранить по дате":
        sheet_id = USER_CURRENT_SHEET.get(user_id)
        if not sheet_id:
            await update.message.reply_text("Сначала выберите файл (кнопка ниже).")
            return
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "copy_by_date": True}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Файл скопирован! {data['message']}")
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message', 'Неизвестная ошибка')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка GAS: {e}")
    else:
        await set_new_date(update, context)

# === Flask интеграция с PTB ===
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        fut = asyncio.run_coroutine_threadsafe(
            application.process_update(update), ptb_loop
        )
        fut.result(timeout=30)
    except Exception as ex:
        logger.error(f"PTB обработка update завершилась с ошибкой: {ex}")
        logger.error(traceback.format_exc())
    return "ok"

# Для health-check
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "ok", 200

def run_flask():
    app.run(host="0.0.0.0", port=10000)

def run_ptb():
    ptb_loop.run_until_complete(application.initialize())
    ptb_loop.run_until_complete(application.start())
    ptb_loop.run_forever()

def main():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    ptb_thread = threading.Thread(target=run_ptb, daemon=True)
    ptb_thread.start()

    logger.info("Бот запущен. Ждём события на вебхуке.")
    run_flask()

if __name__ == "__main__":
    main()

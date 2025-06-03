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
SHEET_IDS = {
    "2": "1sJnM4Rc9eBqINgy-yFRGLBiv3y6R9Sh-aI_uQ9L7ItI",
    "3": "1czq9G66AwmUTeT1lcqCNfZAweF2FwIEa91fAaiOKGp8",
    "4": "1wdmm4o5Q6j9HCYD18BTpruUqJK8ErL7F4WI1KwupE7E",
    "5": "1pRomG_o3T4a6N0ASPq-zlrIv_0hQ7EODZYmdU0iz33U",
}
USER_CURRENT_SHEET = {}  # user_id -> spreadsheet_id

# === Защищённые user_id ===
ALLOWED_USERS = {527852428, 1411866927}

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
        ["Очистить vacancies", "Проверить файлы"]
    ],
    resize_keyboard=True
)

def get_user_id(update: Update):
    return update.message.from_user.id if update.message else None

def get_current_sheet_id(user_id):
    return USER_CURRENT_SHEET.get(user_id, SHEET_IDS["5"])  # по умолчанию файл 5

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_id(update) not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text(
        "Добро пожаловать! Выбери действие:", reply_markup=main_keyboard
    )

async def choose_file(update: Update, context: ContextTypes.DEFAULT_TYPE, file_key):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    USER_CURRENT_SHEET[user_id] = SHEET_IDS[file_key]
    await update.message.reply_text(f"Выбран файл №{file_key}")

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    sheet_id = get_current_sheet_id(user_id)
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "get_date": True}, timeout=15)
        data = resp.json()
        if data.get("date"):
            await update.message.reply_text(f"Текущая дата: {data['date']}\nКакую дату ставим?")
        else:
            await update.message.reply_text(f"Ошибка GAS: {data}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка соединения с таблицей: {e}")

async def update_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    sheet_id = get_current_sheet_id(user_id)
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "update_intervals": True}, timeout=15)
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text("Интервалы успешно обновлены!")
        else:
            await update.message.reply_text(f"Ошибка обновления: {data.get('message', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка GAS: {e}")

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Бот будет перезапущен...")
    await context.application.stop()
    sys.exit(0)

async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    sheet_id = get_current_sheet_id(user_id)
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "get_status": True}, timeout=15)
        data = resp.json()
        if data.get("status") == "ok":
            msg = (
                f"Дата обработки: {data.get('process_date','')}\n"
                f"Сумма result: {data.get('sum_result','')}\n"
                f"Последняя дата: {data.get('last_date_time','')}\n"
                f"Всего интервалов: {data.get('total_intervals','')}\n"
                f"Обработано: {data.get('processed_intervals','')}"
            )
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"Ошибка: {data.get('message', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении состояния: {e}")

async def set_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    if not update.message or not update.message.text:
        return
    new_date = update.message.text.strip()
    import re
    if re.match(r"^([0-2][0-9]|3[0-1])\.(0[1-9]|1[0-2])\.(\d{4})$", new_date):
        sheet_id = get_current_sheet_id(user_id)
        try:
            resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "new_date": new_date}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok":
                await update.message.reply_text(f"Новая дата {new_date} установлена")
            else:
                await update.message.reply_text(f"Ошибка: {data.get('message', 'Неизвестная ошибка')}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при установке даты: {e}")

async def clear_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    sheet_id = get_current_sheet_id(user_id)
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "clear_vacancies": True}, timeout=15)
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text("Лист Vacancies успешно очищен!")
        else:
            await update.message.reply_text(f"Ошибка очистки: {data.get('message', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка GAS: {e}")

async def copy_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    sheet_id = get_current_sheet_id(user_id)
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "copy_by_date": True}, timeout=15)
        data = resp.json()
        if data.get("status") == "ok":
            await update.message.reply_text(f"Файл скопирован! {data['file']}")
        else:
            await update.message.reply_text(f"Ошибка: {data.get('message', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка GAS: {e}")

async def list_saved_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
        return
    sheet_id = get_current_sheet_id(user_id)
    try:
        resp = requests.post(GAS_WEB_APP_URL, json={"spreadsheet_id": sheet_id, "list_files": True}, timeout=15)
        data = resp.json()
        if data.get("status") == "ok":
            files = data.get("files", [])
            if not files:
                await update.message.reply_text("Файлов не найдено в папке 'Загруженные дни'.")
            else:
                msg = "Последние файлы в папке \"Загруженные дни\":\n"
                for file in files[:5]:
                    msg += f"- {file['name']} ({file['created']})\n"
                msg += "Если нужного файла нет — повторите попытку позже."
                await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"Ошибка: {data.get('message', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка GAS: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = get_user_id(update)
    text = update.message.text.strip().lower()
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа.")
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
        await clear_vacancies(update, context)
    elif text == "сохранить по дате":
        await copy_by_date(update, context)
    elif text == "проверить файлы":
        await list_saved_files(update, context)
    elif text.startswith("выбрать файл"):
        num = text.replace("выбрать файл", "").strip()
        if num in SHEET_IDS:
            await choose_file(update, context, num)
        else:
            await update.message.reply_text("Такого файла нет.")
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

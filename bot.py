from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from weather import fetch_open_meteo, fetch_weatherapi, fetch_visual_crossing, aggregate_all, print_table
import json

# === Загрузка конфигурации ===
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

BOT_TOKEN = CONFIG["telegram_bot_token"]

# === Временное хранилище состояния пользователей ===
user_state = {}

# === Старт ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Почасовой прогноз", callback_data="type_hourly")],
        [InlineKeyboardButton("📊 Общая сводка", callback_data="type_summary")]
    ]
    await update.message.reply_text(
        "Привет! Выбери, что показать:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Обработка выбора типа прогноза ===
async def choose_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_state[query.from_user.id] = {"type": query.data}

    keyboard = [
        [InlineKeyboardButton("1 час", callback_data="interval_1")],
        [InlineKeyboardButton("3 часа", callback_data="interval_3")],
        [InlineKeyboardButton("6 часов", callback_data="interval_6")],
        [InlineKeyboardButton("12 часов", callback_data="interval_12")],
        [InlineKeyboardButton("Сутки", callback_data="interval_24")],
        [InlineKeyboardButton("3 дня", callback_data="interval_72")],
        [InlineKeyboardButton("Неделя", callback_data="interval_168")]
    ]
    await query.edit_message_text(
        "Выбери интервал:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Обработка выбора интервала ===
async def choose_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    hours = int(query.data.split("_")[1])
    user_state[query.from_user.id]["hours"] = hours

    keyboard = [
        [InlineKeyboardButton("Все источники", callback_data="source_all")],
        [InlineKeyboardButton("Open-Meteo", callback_data="source_openmeteo")],
        [InlineKeyboardButton("WeatherAPI", callback_data="source_weatherapi")],
        [InlineKeyboardButton("Visual Crossing", callback_data="source_visualcrossing")]
    ]
    await query.edit_message_text(
        "Выбери источник:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Получение и вывод данных ===
async def show_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    source = query.data
    state = user_state[query.from_user.id]

    start_date = datetime.utcnow()
    end_date = start_date + timedelta(hours=state["hours"])

    summaries = []
    if state["type"] == "type_summary": mode = "default"
    elif state["type"] == "type_hourly": mode = "hourly"
    if source == "source_openmeteo":
        summaries.append(fetch_open_meteo(start_date, end_date, mode))
    elif source == "source_weatherapi":
        summaries.append(fetch_weatherapi(start_date, end_date, mode))
    elif source == "source_visualcrossing":
        summaries.append(fetch_visual_crossing(start_date, end_date, mode))
    else:
        summaries.extend([
            fetch_open_meteo(start_date, end_date, mode),
            fetch_weatherapi(start_date, end_date, mode),
            fetch_visual_crossing(start_date, end_date, mode)
        ])
        summaries = [s for s in summaries if s]

    if state["type"] == "type_summary" and len(summaries) > 1:
        summaries.append(aggregate_all(summaries))
    if state["type"] == "type_summary":
        text = f"Погода с {start_date:%Y-%m-%d %H:%M} по {end_date:%Y-%m-%d %H:%M} UTC\n\n"
        for s in summaries:
            text += (
                f"🌍 {s['source']}\n"
                f"Температура: {s['avg_temp']:.1f}°C (min {s['min_temp']:.1f}°C / max {s['max_temp']:.1f}°C)\n"
                f"Ветер: {s['avg_wind']:.1f} м/с\n"
                f"Осадки: {s['avg_rain']:.0f}%\n"
               f"Условия: {', '.join(s['conditions'])}\n\n"
            )
    if state["type"] == "type_hourly":
        text = print_table(summaries)
        #text = format_table_for_telegram(summaries)

    await query.edit_message_text(text)

# === Запуск бота ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_interval, pattern="^type_"))
    app.add_handler(CallbackQueryHandler(choose_source, pattern="^interval_"))
    app.add_handler(CallbackQueryHandler(show_weather, pattern="^source_"))

    app.run_polling()

if __name__ == "__main__":
    main()

import os
import json
import requests
from datetime import datetime, timedelta, timezone
import argparse
from my_logger import Logger
from zoneinfo import ZoneInfo

# === Константы кеша ===
CACHE_FILE = ".weather_cache.json"
CACHE_TTL = timedelta(hours=1)  # время жизни кеша

# === Инициализация логгера ===
logger = Logger(level="DEBUG")

# === Функции кеша ===
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_from_cache(key):
    cache = load_cache()
    if key in cache:
        entry = cache[key]
        ts = datetime.fromisoformat(entry["timestamp"])
        if datetime.utcnow() - ts < CACHE_TTL:
            logger.debug(f"Данные для {key} взяты из кеша")
            return entry["data"]
    return None

def set_to_cache(key, data):
    cache = load_cache()
    cache[key] = {"timestamp": datetime.utcnow().isoformat(), "data": data}
    save_cache(cache)

def cached_request(key, url):
    data = get_from_cache(key)
    if data:
        return data
    try:
        data = requests.get(url, timeout=10).json()
        set_to_cache(key, data)
        return data
    except Exception as e:
        logger.error(f"Ошибка запроса {key}: {e}")
        return None

# === Загрузка конфига ===
logger.info("Загрузка конфигурации из config.json")
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

CITY = CONFIG["city"]
LAT = CONFIG["latitude"]
LON = CONFIG["longitude"]
LANG = CONFIG["lang"]
UNITS = CONFIG["units"]

# === Параметры времени из аргументов ===
def parse_args():
    parser = argparse.ArgumentParser(description="Агрегатор прогноза погоды из нескольких источников")
    parser.add_argument("--start", type=str, help="Дата начала в формате YYYY-MM-DD (по умолчанию сегодня)")
    parser.add_argument("--end", type=str, help="Дата конца в формате YYYY-MM-DD (по умолчанию start + 1 день)")
    return parser.parse_args()

args = parse_args()

if args.start:
    start_date = datetime.strptime(args.start, "%Y-%m-%d")
else:
    start_date = datetime.utcnow()

if args.end:
    end_date = datetime.strptime(args.end, "%Y-%m-%d") + timedelta(days=1)
else:
    end_date = start_date + timedelta(days=1)

logger.info(f"Запрашиваем прогноз с {start_date.date()} по {(end_date - timedelta(days=1)).date()} для {CITY}")

# === Универсальная обработка данных ===
def summarize(source_name, temps, winds, rain_probs, conditions, times, mode="default"):
    if not temps:
        logger.warning(f"Нет данных от источника {source_name}")
        return None
    logger.debug(f"Агрегированы данные от {source_name}")
    if mode == "default":
        return {
            "source": source_name,
            "avg_temp": sum(temps) / len(temps),
            "min_temp": min(temps),
            "max_temp": max(temps),
            "avg_wind": sum(winds) / len(winds),
            "avg_rain": sum(rain_probs) / len(rain_probs) if rain_probs else 0,
            "conditions": list(set(filter(None, conditions)))
        }
    else:
        return {
           "source": source_name,
           "temps": temps,
           "winds": winds,
           "rain_probs": rain_probs ,
           "conditions": conditions,
           "times": times
        }

# === API-источники ===
def fetch_open_meteo(start_date=start_date, end_date=end_date, mode="default"):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation_probability,windspeed_10m&forecast_days=16&timezone=UTC"
    logger.debug(f"Запрос к Open-Meteo: {url}")
    data = cached_request("open_meteo", url)
    if not data:
        return None

    temps, winds, conditions, rain_probs, times = [], [], [], [], []
    for t, temp, rain, wind in zip(
        data["hourly"]["time"],
        data["hourly"]["temperature_2m"],
        data["hourly"]["precipitation_probability"],
        data["hourly"]["windspeed_10m"]
    ):
        time_obj = datetime.fromisoformat(t)
        time_obj = time_obj.replace(tzinfo=timezone.utc)
        if start_date <= time_obj < end_date:
            temps.append(temp)
            winds.append(wind)
            rain_probs.append(rain)
            conditions.append("")
            times.append(time_obj.isoformat())
    return summarize("Open-Meteo", temps, winds, rain_probs, conditions, times, mode=mode)

def fetch_weatherapi(start_date=start_date, end_date=end_date, mode="default"):
    key = CONFIG["apis"]["weatherapi"]["key"]
    url = f"http://api.weatherapi.com/v1/forecast.json?key={key}&q={CITY}&days=10&aqi=no&alerts=no&lang={LANG}"
    logger.debug(f"Запрос к WeatherAPI: {url}")
    data = cached_request("weatherapi", url)
    if not data:
        return None

    temps, winds, conditions, rain_probs, times = [], [], [], [], []
    for day in data["forecast"]["forecastday"]:
        for hour in day["hour"]:
            time_obj = datetime.fromtimestamp(hour["time_epoch"], tz=ZoneInfo("Etc/GMT-10"))
            time_obj = time_obj.astimezone(timezone.utc)
            if start_date <= time_obj < end_date:
                temps.append(hour["temp_c"])
                winds.append(hour["wind_kph"] / 3.6)
                rain_probs.append(hour["chance_of_rain"])
                conditions.append(hour["condition"]["text"])
                times.append(time_obj.isoformat())
    return summarize("WeatherAPI", temps, winds, rain_probs, conditions, times, mode=mode)

def fetch_visual_crossing(start_date=start_date, end_date=end_date, mode="default"):
    key = CONFIG["apis"]["visual_crossing"]["key"]
    date_range = f"{start_date.date()}/{(end_date + timedelta(days=7)).date()}"
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{CITY}/{date_range}?unitGroup=metric&include=hours&key={key}&lang={LANG}"
    logger.debug(f"Запрос к Visual Crossing: {url}")
    data = cached_request("visual_crossing", url)
    if not data:
        return None

    temps, winds, conditions, rain_probs, times = [], [], [], [], []
    for day in data.get("days", []):
        date_str = day["datetime"]
        for hour in day["hours"]:
            full_time = datetime.fromtimestamp(hour['datetimeEpoch'], tz=ZoneInfo("Etc/GMT-10"))
            full_time = full_time.astimezone(timezone.utc)
            if start_date <= full_time < end_date:
                temps.append(hour["temp"])
                winds.append(hour["windspeed"])
                rain_probs.append(hour.get("precipprob", 0))
                conditions.append(hour.get("conditions", ""))
                times.append(full_time.isoformat())
    return summarize("Visual Crossing", temps, winds, rain_probs, conditions, times, mode=mode)

# === Итоговая агрегация ===
def aggregate_all(summaries):
    all_temps, all_winds, all_rains, all_conditions = [], [], [], []
    for s in summaries:
        all_temps.append(s["avg_temp"])
        all_winds.append(s["avg_wind"])
        all_rains.append(s["avg_rain"])
        all_conditions.extend(s["conditions"])
    logger.info("Выполнена финальная агрегация данных")
    return {
        "source": "Среднее по всем",
        "avg_temp": sum(all_temps) / len(all_temps),
        "min_temp": min(s["min_temp"] for s in summaries),
        "max_temp": max(s["max_temp"] for s in summaries),
        "avg_wind": sum(all_winds) / len(all_winds),
        "avg_rain": sum(all_rains) / len(all_rains),
        "conditions": list(set(filter(None, all_conditions)))
    }

# === Красивый вывод ===
def print_table(summaries, start_date=start_date, end_date=end_date):
    final_text = ''
    final_text += f"Прогноз с {start_date:%Y-%m-%d %H:%M} по {end_date:%Y-%m-%d %H:%M} для {CITY}\n"
    final_text += f"{"Время":<30} {'Источник':<20} {'Температура':>6} {'Ветер':>8} {'Осадки':>8}  Условия\n"
    final_text += "-" * 100 + "\n"
    logger.debug(f"Значение summaries: {summaries}")
    for s in summaries:
        for t in range(len(s['temps'])):
            final_text += f"{s['times'][t]:<30} {s['source']:<20} {s['temps'][t]:>6.1f} "
            final_text += f"{s['winds'][t]:>8.1f} {s['rain_probs'][t]:>8.0f}%  {s['conditions'][t]}\n"
        final_text += "-" * 100 + "\n"
    return final_text

if __name__ == "__main__":
    logger.info("Запуск программы")
    sources = [
        fetch_open_meteo(),
        fetch_weatherapi(),
        fetch_visual_crossing()
    ]
    sources = [s for s in sources if s]
    if sources:
        avg_summary = aggregate_all(sources)
        sources.append(avg_summary)
        print(print_table(sources))
    else:
        logger.error("Не удалось получить данные ни от одного источника")

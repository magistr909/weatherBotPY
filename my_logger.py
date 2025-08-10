import os
import datetime

class Logger:
    COLORS = {
        "DEBUG": "\033[94m",     # Синий
        "INFO": "\033[92m",      # Зеленый
        "WARNING": "\033[93m",   # Желтый
        "ERROR": "\033[91m",     # Красный
        "CRITICAL": "\033[95m",  # Фиолетовый
        "RESET": "\033[0m"       # Сброс
    }

    LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(self, log_dir="logs", log_file="app.log", level="DEBUG"):
        self.level = level.upper()
        os.makedirs(log_dir, exist_ok=True)
        self.file_path = os.path.join(log_dir, log_file)

    def _should_log(self, level):
        return self.LEVELS.index(level) >= self.LEVELS.index(self.level)

    def _format_message(self, level, message):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{now} [{level}] {message}"

    def _write(self, message, color=None):
        # В файл
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")
        # В консоль с цветом
        if color:
            print(color + message + self.COLORS["RESET"])
        else:
            print(message)

    def log(self, level, message):
        level = level.upper()
        if self._should_log(level):
            formatted = self._format_message(level, message)
            self._write(formatted, self.COLORS.get(level))

    def debug(self, message): self.log("DEBUG", message)
    def info(self, message): self.log("INFO", message)
    def warning(self, message): self.log("WARNING", message)
    def error(self, message): self.log("ERROR", message)
    def critical(self, message): self.log("CRITICAL", message)


# Пример использования:
if __name__ == "__main__":
    logger = Logger(level="DEBUG")
    logger.debug("Это отладочное сообщение")
    logger.info("Приложение запущено")
    logger.warning("Низкое место на диске")
    logger.error("Не удалось подключиться к базе данных")
    logger.critical("Критическая ошибка — завершение работы")

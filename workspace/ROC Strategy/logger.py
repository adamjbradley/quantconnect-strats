# region imports
from AlgorithmImports import *
# endregion

class LoggerMixin:
    # Define log levels
    LEVELS = {
        "trace": 0,
        "debug": 1,
        "info": 2,
        "warn": 3,
        "error": 4,
        "fatal": 5,
        "off": 6
    }

    def __init__(self, algorithm, threshold="info"):
        self.algorithm = algorithm
        self.set_log_level(threshold)

    def set_log_level(self, level: str):
        self.log_level = self.LEVELS.get(level.lower(), self.LEVELS["info"])

    def log(self, message: str, level: str = "info"):
        current_level = self.LEVELS.get(level.lower(), self.LEVELS["info"])
        if current_level < self.log_level:
            return  # Skip logging below threshold

        # Route the message based on level
        if level.lower() in ("trace", "debug"):
            self.algorithm.Debug(message)
        elif level.lower() in ("warn", "warning"):
            self.algorithm.Log(f"[WARN] {message}")
        elif level.lower() == "error":
            self.algorithm.Error(f"[ERROR] {message}")
        elif level.lower() == "fatal":
            self.algorithm.Error(f"[FATAL] {message}")
        else:
            self.algorithm.Log(message)
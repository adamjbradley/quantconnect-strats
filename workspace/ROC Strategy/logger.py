# region imports
from AlgorithmImports import *
# endregion
class LoggerMixin:
    def __init__(self, algorithm):
        self.algorithm = algorithm

    def log(self, message, level="info"):
        if level == "debug":
            self.algorithm.Debug(message)
        elif level == "error":
            self.algorithm.Error(message)
        else:
            self.algorithm.Log(message)

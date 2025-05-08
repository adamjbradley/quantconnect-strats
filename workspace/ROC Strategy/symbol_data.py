from AlgorithmImports import *

class SymbolData:
    def __init__(self, algorithm, symbol, roc_lookback, volume_window):
        self.symbol = symbol
        self.algorithm = algorithm
        self.roc = RateOfChange(roc_lookback)
        self.roc_lookback = roc_lookback
        self.volume_window = volume_window
        self.roc_window = RollingWindow[float](roc_lookback + 5)
        self.volume_window_data = RollingWindow[float](volume_window)
        self.avg_volume = SimpleMovingAverage(volume_window)
        self.atr = algorithm.ATR(symbol, 14, MovingAverageType.SIMPLE, Resolution.DAILY)
        self.sma_50 = SimpleMovingAverage(50)
        self.sma_200 = SimpleMovingAverage(200)
        self.price = None

        algorithm.RegisterIndicator(symbol, self.roc, Resolution.DAILY)
        algorithm.RegisterIndicator(symbol, self.atr, Resolution.DAILY)
        algorithm.RegisterIndicator(symbol, self.avg_volume, Resolution.DAILY, Field.Volume)
        algorithm.RegisterIndicator(symbol, self.sma_50, Resolution.DAILY)
        algorithm.RegisterIndicator(symbol, self.sma_200, Resolution.DAILY)

    def update(self, bar):
        self.roc_window.add(bar.Close)
        self.volume_window_data.add(bar.Volume)
        
    def is_ready(self):
        return self.roc_window.is_ready and self.volume_window_data.is_ready and self.atr.is_ready

    def roc_today(self):
        return ((self.roc_window[0] - self.roc_window[self.roc_lookback]) / self.roc_window[self.roc_lookback]) * 100

    def roc_yesterday(self):
        return ((self.roc_window[1] - self.roc_window[self.roc_lookback + 1]) / self.roc_window[self.roc_lookback + 1]) * 100

    def roc_3days_ago(self):
        return ((self.roc_window[3] - self.roc_window[self.roc_lookback + 3]) / self.roc_window[self.roc_lookback + 3]) * 100

    def average_volume(self):
        if not self.volume_window_data.is_ready:
            return 0
        total_volume = sum(self.volume_window_data)
        return total_volume / self.volume_window_data.count

    def current_volume(self):
        return self.volume_window_data[0] if self.volume_window_data.is_ready else 0

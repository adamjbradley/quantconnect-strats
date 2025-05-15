# region imports
from AlgorithmImports import *
# endregion

from scipy.ndimage import gaussian_filter1d

class AscendingTriangleDetector:
    def __init__(self, window_size=30, smoothing_sigma=2):
        self.window_size = window_size
        self.smoothing_sigma = smoothing_sigma
        self.prices = []

    def update(self, price):
        self.prices.append(price)
        if len(self.prices) > self.window_size:
            self.prices.pop(0)

    def is_ready(self):
        return len(self.prices) == self.window_size

    def detect(self):
        if not self.is_ready():
            return False
        try:
            smoothed = gaussian_filter1d(self.prices, sigma=max(0.1, self.smoothing_sigma))
            highs = [max(smoothed[i:i+3]) for i in range(len(smoothed) - 3)]
            lows = [min(smoothed[i:i+3]) for i in range(len(smoothed) - 3)]
            if len(highs) < 2 or len(lows) < 2:
                return False
            flat_resistance = abs(highs[-1] - highs[0]) / highs[0] < 0.03
            rising_support = lows[-1] > lows[0]
            return flat_resistance and rising_support
        except:
            return False

    def name(self):
        return f"Ascending Triangle (σ={self.smoothing_sigma})"

    def direction(self):
        return "long"

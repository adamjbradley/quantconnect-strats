# region imports
from AlgorithmImports import *
# endregion

from scipy.ndimage import gaussian_filter1d

class FlagDetector:
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
            smoothed = gaussian_filter1d(self.prices, sigma=max(0.1, float(self.smoothing_sigma)))
            return False  # placeholder logic
        except:
            return False

    def name(self):
        return "Flag (σ=" + str(self.smoothing_sigma) + ")"

    def direction(self):
        return "long"

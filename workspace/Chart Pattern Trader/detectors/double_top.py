# region imports
from AlgorithmImports import *
# endregion

from scipy.ndimage import gaussian_filter1d

class DoubleTopDetector:
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
            half = len(smoothed) // 2
            peak1 = max(smoothed[:half])
            peak2 = max(smoothed[half:])
            if abs(peak1 - peak2) / peak1 < 0.03:
                mid_trough = min(smoothed[half - 2:half + 2])
                if mid_trough < peak1 * 0.97:
                    return True
            return False
        except:
            return False

    def name(self):
        return f"Double Top (σ={self.smoothing_sigma})"

    def direction(self):
        return "short"

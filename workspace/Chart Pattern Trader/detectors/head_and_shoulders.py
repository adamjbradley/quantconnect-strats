# region imports
from AlgorithmImports import *
# endregion

from scipy.ndimage import gaussian_filter1d

class HeadAndShouldersDetector:
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
            mid = len(smoothed) // 2
            left = smoothed[:mid]
            right = smoothed[mid:]
            l_peak = max(left)
            r_peak = max(right)
            head = max(smoothed)
            l_idx = smoothed.tolist().index(l_peak)
            h_idx = smoothed.tolist().index(head)
            r_idx = smoothed.tolist().index(r_peak)
            if not (l_idx < h_idx < r_idx):
                return False
            if head < l_peak * 1.05 or head < r_peak * 1.05:
                return False
            if abs(l_peak - r_peak) / head > 0.1:
                return False
            return True
        except:
            return False

    def name(self):
        return f"Head and Shoulders (σ={self.smoothing_sigma})"

    def direction(self):
        return "short"

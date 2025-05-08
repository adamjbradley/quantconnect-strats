from AlgorithmImports import *

class CustomSlippageModel:
    def __init__(self, slippage_percent=0.0005):
        self.slippage_percent = slippage_percent

    def GetSlippageApproximation(self, asset: Security, order: Order) -> float:
        price = asset.Price
        direction = 1 if order.Direction == OrderDirection.Buy else -1
        return direction * price * self.slippage_percent
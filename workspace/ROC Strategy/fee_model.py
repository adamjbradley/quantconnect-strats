from AlgorithmImports import *

class CustomFeeModel(FeeModel):
    def __init__(self, fixed_fee=1.00, percentage=0.001):  # e.g., $1 fixed + 0.1%
        self.fixed_fee = fixed_fee
        self.percentage = percentage

    def GetOrderFee(self, parameters: OrderFeeParameters) -> OrderFee:
        order = parameters.Order
        security = parameters.Security
        fee_currency = security.QuoteCurrency.Symbol

        # Fee = fixed + percentage of total order value
        order_value = abs(order.Quantity) * security.Price
        total_fee = self.fixed_fee + order_value * self.percentage

        return OrderFee(CashAmount(total_fee, fee_currency))
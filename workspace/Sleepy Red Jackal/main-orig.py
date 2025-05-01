# region imports
from AlgorithmImports import *
# endregion

class SleepyRedJackal(QCAlgorithm):

    def initialize(self):
        self.set_start_date(1998,1,1)
        self.set_end_date(2014,6,1)

        self.set_cash(100000)
        self.add_equity("SPY", Resolution.DAILY)
        self.add_equity("BND", Resolution.DAILY)
        self.add_equity("AAPL", Resolution.DAILY)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            self.set_holdings("SPY", 0.33)
            self.set_holdings("BND", 0.33)
            self.set_holdings("AAPL", 0.33)

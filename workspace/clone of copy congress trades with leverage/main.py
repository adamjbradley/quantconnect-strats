# region imports
from AlgorithmImports import *
# endregion

class LeveragedCopyCongressAlgorithm(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_cash(100000)
        self._universe = self.add_universe(
            QuiverQuantCongressUniverse, 
            lambda constituents: [c.symbol for c in constituents if c.transaction == OrderDirection.BUY]
        )
        spy = Symbol.create('SPY', SecurityType.EQUITY, Market.USA)
        self.schedule.on(self.date_rules.week_start(spy), self.time_rules.after_market_open(spy, 30), self._trade)

    def _trade(self):
        if self._universe.selected is not None:
            symbols = list(self._universe.selected)
            if len(symbols) == 0: return
            inv_volatility_by_symbol = 1 / self.history(symbols, timedelta(6*30), Resolution.DAILY)['close'].unstack(0).pct_change().iloc[1:].std()
            targets = [
                PortfolioTarget(symbol, min(0.1, 1.5 * (inv_volatility_by_symbol[symbol] / inv_volatility_by_symbol.sum())) )
                for symbol in symbols 
                if symbol in inv_volatility_by_symbol
            ]
            self.set_holdings(targets, True)

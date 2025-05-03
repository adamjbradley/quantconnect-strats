from AlgorithmImports import *
from Selection.ETFConstituentsUniverseSelectionModel import ETFConstituentsUniverseSelectionModel

class ROCReboundStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2015, 5, 1)
        self.SetCash(100000)
        self.lookback = 14
        self.max_holding_bars = 15  # Number of bars to hold a position

        self.log_level = 1  # 0 = Off, 1 = Key Events, 2 = Verbose
        self.trade_allocation_pct = 0.01  # Percent of cash to allocate per trade

        self.symbols = []
        self.to_buy = {}  # {symbol: signal_date}
        self.open_positions = {}  # {symbol: {'entry_bar_count': int, 'target': float, 'stop': float}}
        self.atr_indicators = {}

        # Add ETF constituents universe (e.g., SPY)
        symbol = Symbol.Create("SPY", SecurityType.Equity, Market.USA)
        self.AddUniverseSelection(ETFConstituentsUniverseSelectionModel(symbol))

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.At(10, 0), self.Evaluate)
        self.SetWarmUp(self.lookback + 5, Resolution.Daily)

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            self.log(1, f"Added: {security.Symbol}")
            self.symbols.append(security.Symbol)
        for security in changes.RemovedSecurities:
            self.log(1, f"Removed: {security.Symbol}")
            if security.Symbol in self.symbols:
                self.symbols.remove(security.Symbol)

    def log(self, level: int, message: str):
        if self.log_level >= level:
            self.Debug(message)

    def Evaluate(self):
        if self.IsWarmingUp:
            return

        for symbol in self.symbols:
            # Ensure the symbol is added to the algorithm
            if not self.Securities.ContainsKey(symbol):
                self.AddEquity(symbol.Value, Resolution.Daily)

            # Proceed only if the symbol is now registered
            if symbol not in self.atr_indicators:
                self.atr_indicators[symbol] = self.ATR(symbol, 14, MovingAverageType.Simple, Resolution.Daily)

            history = self.History(symbol, self.lookback + 4, Resolution.Daily)
            if history.empty or len(history) < self.lookback + 4:
                self.log(2, f"{symbol.Value}: Not enough history")
                continue

            closes = history["close"]
            close_today = closes.iloc[-1]
            close_past = closes.iloc[-(self.lookback + 1)]
            close_yest = closes.iloc[-2]
            close_yest_past = closes.iloc[-(self.lookback + 2)]
            close_3ago = closes.iloc[-4]
            close_3ago_past = closes.iloc[-(self.lookback + 4)]

            if close_past == 0 or close_yest_past == 0 or close_3ago_past == 0:
                continue

            roc_today = ((close_today - close_past) / close_past) * 100
            roc_yesterday = ((close_yest - close_yest_past) / close_yest_past) * 100
            roc_3days_ago = ((close_3ago - close_3ago_past) / close_3ago_past) * 100

            deep_drop = roc_today < -20

            if deep_drop and roc_today > roc_3days_ago and roc_today > roc_yesterday:
                if not self.Portfolio[symbol].Invested and symbol not in self.to_buy and symbol not in self.open_positions:
                    self.log(1, f"{self.Time.date()} {symbol.Value} | ROC: {roc_today:.1f}>{roc_yesterday:.1f}, {roc_3days_ago:.1f}")
                    self.to_buy[symbol] = self.Time.date()
                    self.log(1, f"{self.Time.date()} SIGNAL {symbol.Value} — Buy scheduled for next day")

    def OnData(self, data: Slice):
        # Increment bar count for open positions
        for symbol in list(self.open_positions.keys()):
            position = self.open_positions[symbol]
            position['entry_bar_count'] += 1

            # Check if holding period has reached max_holding_bars
            if position['entry_bar_count'] >= self.max_holding_bars:
                self.Liquidate(symbol)
                self.log(1, f"{self.Time.date()} SELL {symbol.Value} | Held for {self.max_holding_bars} bars")
                self.open_positions.pop(symbol)

        for symbol, signal_date in list(self.to_buy.items()):
            if self.Time.date() <= signal_date:
                continue

            if not self.Portfolio[symbol].Invested and self.Securities[symbol].IsTradable:
                atr = self.atr_indicators[symbol]

                if not atr.IsReady:
                    self.log(2, f"{symbol.Value}: ATR not ready")
                    self.to_buy.pop(symbol)
                    continue

                price = self.Securities[symbol].Price
                if price is None or price <= 0:
                    self.log(1, f"{self.Time.date()} SKIP {symbol.Value} — Invalid or zero price")
                    self.to_buy.pop(symbol)
                    continue

                available_cash = self.Portfolio.Cash
                max_alloc_cash = available_cash * self.trade_allocation_pct
                quantity = int(max_alloc_cash / price)

                if quantity <= 0:
                    self.log(1, f"{self.Time.date()} SKIP {symbol.Value} — Not enough cash for allocation at price {price:.2f}")
                    self.to_buy.pop(symbol)
                    continue

                try:
                    ticket = self.MarketOrder(symbol, quantity)
                    self.log(1, f"{self.Time.date()} ORDER PLACED {symbol.Value} for {quantity} shares | Awaiting fill")
                except Exception as e:
                    self.log(1, f"{self.Time.date()} SKIP {symbol.Value} — Order failed: {e}")
                finally:
                    self.to_buy.pop(symbol)

    def OnOrderEvent(self, order_event: OrderEvent):
        if order_event.Status != OrderStatus.Filled:
            return

        symbol = order_event.Symbol
        if order_event.Direction != OrderDirection.Buy:
            return

        price = order_event.FillPrice
        atr = self.atr_indicators[symbol]
        if not atr.IsReady:
            self.log(1, f"{self.Time.date()} FILLED {symbol.Value} — ATR not ready, skipping open_positions")
            return

        atr_val = atr.Current.Value
        target = price + atr_val
        stop = price - 2.5 * atr_val

        self.open_positions[symbol] = {
            "entry_bar_count": 0,
            "target": target,
            "stop": stop
        }

        self.log(1, f"{self.Time.date()} FILLED {symbol.Value} at {price:.2f} | TP: {target:.2f} | SL: {stop:.2f}")

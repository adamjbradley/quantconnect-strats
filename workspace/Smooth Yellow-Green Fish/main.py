from AlgorithmImports import *

class ROCReboundStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetCash(100000)
        self.lookback = 14

        self.debug_mode = True
        self.log_level = 1  # 0 = Off, 1 = Key Events, 2 = Verbose

        self.symbols = []
        self.to_buy = {}  # {symbol: signal_date}
        self.pending_buys = {}  # {symbol: {weight, signal_date}}
        self.open_positions = {}  # {symbol: {entry, target, stop, entry_date}}
        self.atr_indicators = {}

        self.AddUniverse(self.CoarseSelectionFunction)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.At(10, 0), self.Evaluate)

    def log(self, level: int, message: str):
        if self.log_level >= level:
            self.Debug(message)

    def CoarseSelectionFunction(self, coarse):
        selected = sorted(
            [x for x in coarse if x.HasFundamentalData],
            key=lambda x: -x.DollarVolume
        )[:3000]
        self.symbols = [x.Symbol for x in selected]
        return self.symbols

    def Evaluate(self):
        for symbol in self.symbols:
            if not self.Securities.ContainsKey(symbol):
                self.AddEquity(symbol.Value, Resolution.DAILY)
            if symbol not in self.atr_indicators:
                self.atr_indicators[symbol] = self.ATR(symbol, 14, MovingAverageType.Simple, Resolution.DAILY)

            history = self.History(symbol, self.lookback + 4, Resolution.DAILY)
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

            drop_pct = (close_past - close_today) / close_past * 100
            roc_today = ((close_today - close_past) / close_past) * 100
            roc_yesterday = ((close_yest - close_yest_past) / close_yest_past) * 100
            roc_3days_ago = ((close_3ago - close_3ago_past) / close_3ago_past) * 100

            self.log(2, f"{self.Time.date()} {symbol.Value} | Drop: {drop_pct:.1f}%, ROC: {roc_today:.1f}>{roc_yesterday:.1f}, {roc_3days_ago:.1f}")

            deep_drop = drop_pct > 20

            if deep_drop and roc_today > roc_3days_ago:
                if not self.Portfolio[symbol].Invested and symbol not in self.to_buy and symbol not in self.open_positions:
                    self.to_buy[symbol] = self.Time.date()
                    self.log(1, f"{self.Time.date()} SIGNAL {symbol.Value} — Buy scheduled for next day")

    def OnData(self, data: Slice):
        # 0. Clean up open positions that no longer exist
        for symbol in list(self.open_positions.keys()):
            if not self.Portfolio[symbol].Invested:
                self.open_positions.pop(symbol)

        # 1. Execute scheduled buys
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
                if price <= 0:
                    self.log(1, f"{self.Time.date()} SKIP {symbol.Value} — Price unavailable or zero")
                    self.to_buy.pop(symbol)
                    continue

                available_cash = self.Portfolio.Cash
                max_alloc_cash = available_cash * 0.01  # 1% allocation
                quantity = int(max_alloc_cash / price)

                if quantity <= 0:
                    self.log(1, f"{self.Time.date()} SKIP {symbol.Value} — Not enough cash for 1% allocation at price {price:.2f}")
                    self.to_buy.pop(symbol)
                    continue

                try:
                    ticket = self.MarketOrder(symbol, quantity)
                    self.pending_buys[symbol] = {
                        "quantity": quantity,
                        "signal_date": self.Time.date()
                    }
                    self.log(1, f"{self.Time.date()} ORDER PLACED {symbol.Value} for {quantity} shares | Awaiting fill")
                except Exception as e:
                    self.log(1, f"{self.Time.date()} SKIP {symbol.Value} — Order failed: {e}")
                finally:
                    self.to_buy.pop(symbol)

        # 2. Monitor open positions
        for symbol, pos in list(self.open_positions.items()):
            price = self.Securities[symbol].Price
            target = pos["target"]
            stop = pos["stop"]

            if price >= target:
                self.Liquidate(symbol)
                self.log(1, f"{self.Time.date()} SELL {symbol.Value} at {price:.2f} | TAKE PROFIT ({target:.2f})")
                self.open_positions.pop(symbol)

            elif price <= stop:
                self.Liquidate(symbol)
                self.log(1, f"{self.Time.date()} SELL {symbol.Value} at {price:.2f} | STOP LOSS ({stop:.2f})")
                self.open_positions.pop(symbol)

            else:
                holding_days = (self.Time.date() - pos["entry_date"]).days
                if holding_days > 15:
                    self.Liquidate(symbol)
                    self.log(1, f"{self.Time.date()} SELL {symbol.Value} | MAX HOLDING PERIOD ({holding_days} days)")
                    self.open_positions.pop(symbol)

    def OnOrderEvent(self, order_event: OrderEvent):
        if order_event.Status != OrderStatus.Filled:
            return

        symbol = order_event.Symbol
        if symbol not in self.pending_buys:
            return

        if order_event.Direction != OrderDirection.Buy:
            return

        price = order_event.FillPrice
        atr = self.atr_indicators[symbol]
        if not atr.IsReady:
            self.log(1, f"{self.Time.date()} FILLED {symbol.Value} — ATR not ready, skipping open_positions")
            self.pending_buys.pop(symbol)
            return

        atr_val = atr.Current.Value
        target = price + atr_val
        stop = price - 2.5 * atr_val

        self.open_positions[symbol] = {
            "entry": price,
            "target": target,
            "stop": stop,
            "entry_date": self.Time.date()
        }

        self.log(1, f"{self.Time.date()} FILLED {symbol.Value} at {price:.2f} | TP: {target:.2f} | SL: {stop:.2f}")
        self.pending_buys.pop(symbol)

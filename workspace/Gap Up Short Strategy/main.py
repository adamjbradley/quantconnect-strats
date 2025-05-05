from AlgorithmImports import *

class OvernightGapUpShort(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(self.Time.date())
        self.SetCash(100000)

        self.cap_tiers = [x.strip() for x in (self.GetParameter("capTiers") or "small").split(",")]
        self.gap_threshold = float(self.GetParameter("gapThreshold") or 0.03)
        self.log_level = int(self.GetParameter("logLevel") or 1)
        self.volume_surge_threshold = float(self.GetParameter("volumeSurgeThreshold") or 1.5)

        self.position_size = 0.1
        self.daily_pnl = 0
        self.total_trades = 0
        self.total_pnl = 0

        self.spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        self.UniverseSettings.Resolution = Resolution.Hour
        self.AddUniverse(self.CoarseSelectionFunction)

        self.active_symbols = set()
        self.stop_orders = {}

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen(self.spy, 1), self.CheckOvernightGaps)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose(self.spy, 1), self.ExitPositions)

    def CoarseSelectionFunction(self, coarse):
        return [x.Symbol for x in coarse if x.HasFundamentalData and x.Price > 2][:1000]

    def FineSelectionFunction(self, fine):
        fine = list(fine)

        caps = []
        for tier in self.cap_tiers:
            if tier == "micro":
                caps.append((0, 3e8))
            elif tier == "small":
                caps.append((3e8, 2e9))
            elif tier == "mid":
                caps.append((2e9, 1e10))
            elif tier == "large":
                caps.append((1e10, float("inf")))

        def match_cap(x):
            return any(min_cap <= x.MarketCap <= max_cap for min_cap, max_cap in caps)

        filtered = [x.Symbol for x in fine if match_cap(x) and x.DollarVolume > 1e5 and x.Price > 2][:500]
        self.log(2, f"{self.Time.date()} Selected {len(fine)} fine symbols, {len(filtered)} match capTiers={','.join(self.cap_tiers)}")
        return filtered

    def log(self, level: int, message: str):
        if self.log_level >= level:
            self.Debug(message)

    def CheckOvernightGaps(self):
        self.active_symbols.clear()
        qualified_count = 0

        for symbol in self.ActiveSecurities.Keys:
            history = self.History(symbol, 6, Resolution.Daily)
            if history.empty or "volume" not in history.columns:
                self.log(2, f"{symbol}: history missing or no volume")
                continue
            if history.empty or len(history.index.unique()) < 2:
                self.log(2, f"{symbol}: insufficient history")
                continue

            prev_close = history.iloc[-2]["close"]
            today_open = history.iloc[-1]["open"]
            avg_volume = history.iloc[:-1]["volume"].mean()
            today_volume = history.iloc[-1]["volume"]
            gap = (today_open - prev_close) / prev_close

            if gap >= self.gap_threshold:
                if today_volume <= self.volume_surge_threshold * avg_volume:
                    self.log(2, f"{symbol}: volume surge {today_volume:.0f} vs avg {avg_volume:.0f} below threshold")
                    continue
                qty = self.CalculateOrderQuantity(symbol, -self.position_size)
                ticket = self.MarketOrder(symbol, qty)
                stop_price = self.Securities[symbol].Price * 1.01
                stop = self.StopMarketOrder(symbol, -qty, stop_price)
                self.stop_orders[symbol] = stop
                self.log(1, f"Stop loss set at {stop_price:.2f} for {symbol}")
                self.active_symbols.add(symbol)
                qualified_count += 1
                self.log(1, f"{self.Time} SHORT {symbol} @ {today_open:.2f}, Gap: {gap:.2%}")
            else:
                self.log(2, f"{symbol}: gap {gap:.2%} below threshold")

        self.log(1, f"{self.Time.date()} Qualified gap-up symbols: {qualified_count}")

    def ExitPositions(self):
        self.daily_pnl = 0

        for symbol in list(self.active_symbols):
            if self.Portfolio[symbol].Invested:
                quantity = self.Portfolio[symbol].Quantity
                entry_price = self.Portfolio[symbol].AveragePrice
                exit_price = self.Securities[symbol].Price
                pnl = (entry_price - exit_price) * quantity

                self.daily_pnl += pnl
                self.total_trades += 1
                self.total_pnl += pnl

                self.log(1, f"{self.Time} EXIT {symbol} @ {exit_price:.2f}, Entry={entry_price:.2f}, Qty={quantity}, PnL={pnl:.2f}")
                self.Liquidate(symbol)
                if symbol in self.stop_orders:
                    self.Transactions.CancelOrder(self.stop_orders[symbol].OrderId)
                    self.stop_orders.pop(symbol)

        self.log(1, f"{self.Time.date()} Total daily PnL: {self.daily_pnl:.2f}")

    def OnEndOfAlgorithm(self):
        self.log(1, f"FINAL SUMMARY: Trades={self.total_trades}, Total PnL={self.total_pnl:.2f}")


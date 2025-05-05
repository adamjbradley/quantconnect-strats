from AlgorithmImports import *
from symbol_data import SymbolData
from utils import get_sector_codes, get_market_cap_thresholds

class ROCReboundStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2020, 12, 31)
        self.SetCash(100000)

        self.AddEquity("SPY", Resolution.Daily)
        self.SetBenchmark("SPY")

        self.vix = self.AddData(CBOE, "VIX", Resolution.Daily).Symbol

        self.lookback = 14
        self.volume_window = 20
        self.max_holding_days = 15
        self.trade_allocation_pct = 0.1
        self.PlotROC = True

        cap_tiers_param = self.GetParameter("capTiers") or "small"
        self.cap_tiers = [x.strip().lower() for x in cap_tiers_param.split(",")]

        sector_tiers_param = self.GetParameter("sectorTiers") or "healthcare"
        self.sector_tiers = [x.strip().lower() for x in sector_tiers_param.split(",")]

        self.volume_surge_threshold = float(self.GetParameter("volumeSurgeThreshold") or 1.5)
        self.vix_threshold = float(self.GetParameter("vixThreshold") or 20)
        self.roc_min = float(self.GetParameter("rocMin") or -40)
        self.roc_max = float(self.GetParameter("rocMax") or -15)

        self.Log(f"Parameter: capTiers = {cap_tiers_param}")
        self.Log(f"Parameter: sectorTiers = {sector_tiers_param}")
        self.Log(f"Parameter: volumeSurgeThreshold = {self.volume_surge_threshold}")
        self.Log(f"Parameter: vixThreshold = {self.vix_threshold}")
        self.Log(f"Parameter: rocMin = {self.roc_min}")
        self.Log(f"Parameter: rocMax = {self.roc_max}")

        self.market_cap_thresholds = get_market_cap_thresholds()
        self.sector_name_to_code = get_sector_codes()
        self.sector_codes = [self.sector_name_to_code[name] for name in self.sector_tiers if name in self.sector_name_to_code]

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.symbol_data = {}
        self.to_buy = {}
        self.open_positions = {}

        self.SetWarmUp(self.lookback + self.volume_window)

    def CoarseSelectionFunction(self, coarse):
        return [x.Symbol for x in coarse if x.HasFundamentalData]

    def FineSelectionFunction(self, fine):
        selected = []
        for stock in fine:
            market_cap = stock.MarketCap
            cap_match = any(
                self.market_cap_thresholds[tier][0] <= market_cap <= self.market_cap_thresholds[tier][1]
                for tier in self.cap_tiers
            )

            sector_code = stock.AssetClassification.MorningstarSectorCode
            sector_match = sector_code in self.sector_codes

            if cap_match and sector_match:
                selected.append(stock.Symbol)

        return selected

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolData(self, symbol, self.lookback, self.volume_window)

    def OnData(self, data):
        if self.IsWarmingUp:
            return

        if self.vix in data and data[self.vix] is not None:
            current_vix = data[self.vix].Close
            if current_vix > self.vix_threshold:
                self.Debug(f"High VIX: {current_vix}")
                return
            else:
                self.Debug(f"Normal VIX: {current_vix}")

        for symbol, symbol_data in self.symbol_data.items():
            if symbol in data and data[symbol] is not None:
                symbol_data.update(data[symbol])

        for symbol, symbol_data in self.symbol_data.items():
            if symbol_data.is_ready():
                roc_today = symbol_data.roc_today()
                roc_yesterday = symbol_data.roc_yesterday()
                roc_3days_ago = symbol_data.roc_3days_ago()
                avg_volume = symbol_data.average_volume()
                current_volume = symbol_data.current_volume()

                if self.PlotROC:
                    self.Plot(symbol.Value, "ROC Today", roc_today)
                    self.Plot(symbol.Value, "ROC Yesterday", roc_yesterday)
                    self.Plot(symbol.Value, "ROC 3 Days Ago", roc_3days_ago)

                deep_drop = self.roc_min <= roc_today <= self.roc_max
                volume_surge = current_volume >= self.volume_surge_threshold * avg_volume

                if deep_drop and roc_today > roc_3days_ago and roc_today > roc_yesterday and volume_surge:
                    if not self.Portfolio[symbol].Invested and symbol not in self.to_buy and symbol not in self.open_positions:
                        self.to_buy[symbol] = self.Time.date()

        for symbol, signal_date in list(self.to_buy.items()):
            if self.Time.date() <= signal_date:
                continue

            if not self.Portfolio[symbol].Invested and self.Securities[symbol].IsTradable:
                price = self.Securities[symbol].Price
                if price is None or price <= 0:
                    self.to_buy.pop(symbol)
                    continue

                available_cash = self.Portfolio.Cash
                max_alloc_cash = available_cash * self.trade_allocation_pct
                quantity = int(max_alloc_cash / price)

                if quantity <= 0:
                    self.to_buy.pop(symbol)
                    continue

                try:
                    self.MarketOrder(symbol, quantity)
                except Exception as e:
                    self.Debug(f"Order failed for {symbol.Value}: {e}")
                finally:
                    self.to_buy.pop(symbol)

        for symbol, pos in list(self.open_positions.items()):
            price = self.Securities[symbol].Price
            target = pos["target"]
            stop = pos["stop"]

            if price >= target or price <= stop:
                self.Liquidate(symbol)
                self.open_positions.pop(symbol)
            else:
                holding_days = (self.Time.date() - pos["entry_date"]).days
                if holding_days > self.max_holding_days:
                    self.Liquidate(symbol)
                    self.open_positions.pop(symbol)

    def OnOrderEvent(self, order_event: OrderEvent):
        if order_event.Status != OrderStatus.Filled:
            return

        symbol = order_event.Symbol
        if order_event.Direction != OrderDirection.Buy:
            return

        price = order_event.FillPrice
        atr = self.symbol_data[symbol].atr
        if not atr.IsReady:
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

    def OnEndOfAlgorithm(self):
        self.Liquidate()

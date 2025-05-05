from AlgorithmImports import *
import numpy as np

class ROCReboundStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2015, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100000)

        # Parameters
        self.lookback = 14
        self.volume_window = 20
        self.max_holding_days = 15
        self.trade_allocation_pct = 0.1

        # Retrieve parameters
        self.cap_tiers = [x.strip().lower() for x in (self.GetParameter("capTiers") or "micro, small, mid, large, mega").split(",")]
        self.sector_tiers = [x.strip().lower() for x in (self.GetParameter("sectorTiers") or "basic materials, communication services, consumer cyclical, consumer defensive, consumer defensive, energy, financial services, industrial, real estate, technology, utilities").split(",")]
        self.volume_surge_threshold = float(self.GetParameter("volumeSurgeThreshold") or 1)

        # Define market cap thresholds (in USD)
        self.market_cap_thresholds = {
            'micro': (0, 300e6),
            'small': (300e6, 2e9),
            'mid': (2e9, 10e9),
            'large': (10e9, 200e9),
            'mega': (200e9, float('inf'))
        }

        # Define sector name to MorningstarSectorCode mapping
        self.sector_name_to_code = {
            'basic materials': MorningstarSectorCode.BASIC_MATERIALS,
            'communication services': MorningstarSectorCode.COMMUNICATION_SERVICES,
            'consumer cyclical': MorningstarSectorCode.CONSUMER_CYCLICAL,
            'consumer defensive': MorningstarSectorCode.CONSUMER_DEFENSIVE,
            'energy': MorningstarSectorCode.ENERGY,
            'financial services': MorningstarSectorCode.FINANCIAL_SERVICES,
            'healthcare': MorningstarSectorCode.HEALTHCARE,
            'industrials': MorningstarSectorCode.INDUSTRIALS,
            'real estate': MorningstarSectorCode.REAL_ESTATE,
            'technology': MorningstarSectorCode.TECHNOLOGY,
            'utilities': MorningstarSectorCode.UTILITIES
        }

        # Log parameters
        self.Log(f"Parameter: capTiers = {self.cap_tiers}")
        self.Log(f"Parameter: sectorTiers = {self.sector_tiers}")
        self.Log(f"Parameter: volumeSurgeThreshold = {self.volume_surge_threshold}")
        
        # Map sector names to codes
        self.sector_codes = [self.sector_name_to_code[name] for name in self.sector_tiers if name in self.sector_name_to_code]

        # Add SPY as the benchmark
        self.AddEquity("SPY", Resolution.Daily)
        self.SetBenchmark("SPY")

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)
    
        self.symbol_data = {}
        self.to_buy = {}  # {symbol: signal_date}
        self.open_positions = {}  # {symbol: {entry, target, stop, entry_date}}

        self.SetWarmUp(self.lookback + self.volume_window)

    def CoarseSelectionFunction(self, coarse):
        # Filter for securities with fundamental data
        return [x.Symbol for x in coarse if x.HasFundamentalData]

    def FineSelectionFunction(self, fine):
        selected = []
        for stock in fine:
            # Market cap filter
            market_cap = stock.MarketCap
            cap_match = any(
                self.market_cap_thresholds[tier][0] <= market_cap <= self.market_cap_thresholds[tier][1]
                for tier in self.cap_tiers
            )

            # Sector filter using MorningstarSectorCode
            sector_code = stock.AssetClassification.MorningstarSectorCode
            sector_match = sector_code in self.sector_codes

            if cap_match and sector_match:
                selected.append(stock.Symbol)

        return selected

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            if symbol not in self.symbol_data:
                # Initialize symbol data
                self.symbol_data[symbol] = SymbolData(self, symbol, self.lookback, self.volume_window)

    def OnData(self, data):
        if self.IsWarmingUp:
            return

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

                deep_drop = roc_today < -15 and roc_today > -30
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

class SymbolData:
    def __init__(self, algorithm, symbol, roc_lookback, volume_window):
        self.symbol = symbol
        self.algorithm = algorithm
        self.roc_lookback = roc_lookback
        self.volume_window = volume_window
        self.roc_window = RollingWindow[float](roc_lookback + 5)
        self.volume_window_data = RollingWindow[float](volume_window)
        self.atr = algorithm.ATR(symbol, 14, MovingAverageType.Simple, Resolution.Daily)

    def update(self, bar):
        self.roc_window.Add(bar.Close)
        self.volume_window_data.Add(bar.Volume)

    def is_ready(self):
        return self.roc_window.IsReady and self.volume_window_data.IsReady and self.atr.IsReady

    def roc_today(self):
        return ((self.roc_window[0] - self.roc_window[self.roc_lookback]) / self.roc_window[self.roc_lookback]) * 100

    def roc_yesterday(self):
        return ((self.roc_window[1] - self.roc_window[self.roc_lookback + 1]) / self.roc_window[self.roc_lookback + 1]) * 100

    def roc_3days_ago(self):
        return ((self.roc_window[3] - self.roc_window[self.roc_lookback + 3]) / self.roc_window[self.roc_lookback + 3]) * 100

    def average_volume(self):
        return np.mean([x for x in self.volume_window_data])

    def current_volume(self):
        return self.volume_window_data[0]
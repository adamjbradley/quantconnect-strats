from AlgorithmImports import *

class GapDownReversalWithVIXY(QCAlgorithm):
    def Initialize(self):
        self.start_year = int(self.GetParameter("start_year") or 2021)
        self.start_month = int(self.GetParameter("start_month") or 1)
        self.start_day = int(self.GetParameter("start_day") or 1)
        self.SetStartDate(self.start_year, self.start_month, self.start_day)
        self.end_year = int(self.GetParameter("end_year") or 2021)
        self.end_month = int(self.GetParameter("end_month") or 3)
        self.end_day = int(self.GetParameter("end_day") or 1)
        self.SetEndDate(self.end_year, self.end_month, self.end_day)
        self.initial_cash = float(self.GetParameter("initial_cash") or 100000)
        self.SetCash(int(self.GetParameter("cash") or 100000))

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.min_market_cap = float(self.GetParameter("min_market_cap") or 1e9)  # Minimum market cap filter
        self.max_market_cap = float(self.GetParameter("max_market_cap") or 1e11)  # Maximum market cap filter
        self.allowed_sector_codes = [206, 311, 102]  # Sector codes: Healthcare, Tech, Consumer Cyclical  # Healthcare, Tech, Consumer Cyclical
        self.volume_window = int(self.GetParameter("volume_window") or 20)  # Days of volume history
        self.volume_spike_multiplier = float(self.GetParameter("volume_spike_multiplier") or 1.5)  # Multiplier for volume spike check
        self.atr_period = int(self.GetParameter("atr_period") or 14)  # ATR lookback period
        self.risk_reward = float(self.GetParameter("risk_reward") or 2)  # Risk-reward ratio
        self.log_level = 2  # Verbose logging

        self.vixy_symbol = self.AddEquity("VIXY", Resolution.Daily).Symbol
        self.vix_threshold = 25

        self.symbol_data = {}

    def CoarseSelectionFunction(self, coarse):
        return [x.Symbol for x in coarse if x.HasFundamentalData and x.Market == "usa"][:100]

    def FineSelectionFunction(self, fine):
        return [
            x.Symbol for x in fine
            if x.MarketCap and x.AssetClassification
            and x.AssetClassification.MorningstarSectorCode in self.allowed_sector_codes
            and self.min_market_cap <= x.MarketCap <= self.max_market_cap
        ][:100]

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolData(self, symbol, self.volume_window, self.atr_period)

    def OnData(self, slice):
        vix_price = 20  # Bypassing VIXY filtering for testing

        for symbol, data in self.symbol_data.items():
            if symbol not in slice.Bars or not data.IsReady():
                continue

            bar = slice.Bars[symbol]
            data.Update(bar)

            if not data.in_position:
                if True:  # Bypassing all entry filters for testing
                    atr = data.atr.Current.Value
                    stop = bar.Close - 1.5 * atr
                    tp = bar.Close + self.risk_reward * (bar.Close - stop)

                    vix_normal = max(0.5, min(2.0, 20 / vix_price))
                    position_size = (1 / 50) * vix_normal

                    self.SetHoldings(symbol, position_size)
                    data.SetEntry(bar.Close, stop, tp)
                    self.LogTrade(f"{symbol.Value} LONG @ {bar.Close:.2f}, SL: {stop:.2f}, TP: {tp:.2f}, Size: {position_size:.3f}", level=1)
                else:
                    self.LogTrade(f"{symbol.Value} SKIPPED due to filters", level=2)

            if data.in_position:
                if bar.Close <= data.stop_price or bar.Close >= data.take_profit_price:
                    self.Liquidate(symbol)
                    data.in_position = False
                    self.LogTrade(f"{symbol.Value} EXIT @ {bar.Close:.2f}", level=1)

    def OnEndOfDay(self, symbol):
        if symbol in self.symbol_data:
            self.symbol_data[symbol].ResetDaily()

    def LogTrade(self, message, level=1):
        if self.log_level >= level:
            self.Debug(message)


class SymbolData:
    def __init__(self, algo, symbol, volume_window, atr_period):
        self.symbol = symbol
        self.algo = algo
        self.daily_open = None
        self.previous_close = None
        self.first_hour_volume = 0
        self.atr = algo.ATR(symbol, atr_period, MovingAverageType.Wilders, Resolution.Daily)
        self.volume_history = RollingWindow[float](volume_window)
        self.in_position = False
        self.entry_price = None
        self.stop_price = None
        self.take_profit_price = None

    def Update(self, bar):
        self.daily_open = bar.Open
        self.first_hour_volume = bar.Volume
        history = self.algo.History(self.symbol, 2, Resolution.Daily)
        if not history.empty:
            self.previous_close = history.iloc[-2]["close"]

    def SetEntry(self, entry, stop, tp):
        self.entry_price = entry
        self.stop_price = stop
        self.take_profit_price = tp
        self.in_position = True

    def AvgVolume(self):
        return sum(self.volume_history) / self.volume_history.Count if self.volume_history.Count > 0 else None

    def IsReady(self):
        return self.atr.IsReady and self.previous_close is not None and self.daily_open is not None

    def ResetDaily(self):
        if self.first_hour_volume > 0:
            self.volume_history.Add(self.first_hour_volume)
        self.daily_open = None
        self.previous_close = None
        self.first_hour_volume = 0


from AlgorithmImports import *

class SPYConstituentPinBarStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2023, 12, 31)
        self.SetCash(100000)

        self.UniverseSettings.Resolution = Resolution.Hour
        self.AddUniverseSelection(ETFConstituentsUniverseSelectionModel("SPY", self.UniverseSettings))

        self.symbol_data = {}
        self.lookback = 20
        self.rsi_period = 14
        self.sma_period = 20
        self.stop_loss_pct = 0.01
        self.take_profit_pct = 0.02
        self.min_hourly_dollar_volume = 1_000_000  # Filter out illiquid stocks

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            if symbol not in self.symbol_data:
                # Filter by hourly dollar volume (if available)
                history = self.History(symbol, 2, Resolution.Hour)
                if not history.empty and 'close' in history.columns and 'volume' in history.columns:
                    latest_bar = history.iloc[-1]
                    dollar_volume = latest_bar['close'] * latest_bar['volume']
                    if dollar_volume < self.min_hourly_dollar_volume:
                        continue

                self.symbol_data[symbol] = SymbolData(symbol, self.rsi_period, self.sma_period, self)
                self.Debug(f"Added {symbol}")

        for security in changes.RemovedSecurities:
            symbol = security.Symbol
            if symbol in self.symbol_data:
                self.symbol_data.pop(symbol)
                self.Debug(f"Removed {symbol}")

    def OnData(self, data):
        for symbol, sd in self.symbol_data.items():
            if not sd.IsReady(data):
                continue

            bar = data[symbol] if symbol in data and data[symbol] is not None else None
            if bar is None or bar.Close is None:
                continue

            history = self.History(symbol, self.lookback + 1, Resolution.Hour)
            if history.empty or len(history) < self.lookback + 1:
                continue

            recent = history.iloc[:-1]
            recent_high = recent['high'].max()
            recent_low = recent['low'].min()

            price = bar.Close

            if self.Portfolio[symbol].Invested:
                continue

            # Long setup
            if (sd.IsBullishPinBar(bar) and
                self.NearLevel(bar.Low, recent_low) and
                sd.RSI.Current.Value < 30 and
                price < sd.SMA.Current.Value):
                self.EnterTrade(symbol, bar, True)

            # Short setup
            elif (sd.IsBearishPinBar(bar) and
                  self.NearLevel(bar.High, recent_high) and
                  sd.RSI.Current.Value > 70 and
                  price > sd.SMA.Current.Value):
                self.EnterTrade(symbol, bar, False)

    def NearLevel(self, price, level, tolerance=0.01):
        return abs(price - level) / level < tolerance

    def EnterTrade(self, symbol, bar, is_long):
        quantity = self.CalculateOrderQuantity(symbol, 0.05)
        stop_price = bar.Low * (1 - self.stop_loss_pct) if is_long else bar.High * (1 + self.stop_loss_pct)
        target_price = bar.Close * (1 + self.take_profit_pct) if is_long else bar.Close * (1 - self.take_profit_pct)

        direction = "LONG" if is_long else "SHORT"
        self.Debug(f"{direction} {symbol.Value} at {bar.Close} on {self.Time}")

        if is_long:
            self.MarketOrder(symbol, quantity)
            self.StopMarketOrder(symbol, -quantity, stop_price)
            self.LimitOrder(symbol, -quantity, target_price)
        else:
            self.MarketOrder(symbol, -quantity)
            self.StopMarketOrder(symbol, quantity, stop_price)
            self.LimitOrder(symbol, quantity, target_price)


class SymbolData:
    def __init__(self, symbol, rsi_period, sma_period, algo):
        self.Symbol = symbol
        self.RSI = algo.RSI(symbol, rsi_period, MovingAverageType.Wilders, Resolution.Hour)
        self.SMA = algo.SMA(symbol, sma_period, Resolution.Hour)
        self.algo = algo

    def IsReady(self, data):
        return (self.RSI.IsReady and
                self.SMA.IsReady and
                self.Symbol in data and
                data[self.Symbol] is not None and
                data[self.Symbol].Close is not None)

    def IsBullishPinBar(self, bar):
        body = abs(bar.Close - bar.Open)
        lower_wick = min(bar.Open, bar.Close) - bar.Low
        upper_wick = bar.High - max(bar.Open, bar.Close)
        return lower_wick > 2 * body and upper_wick < body and bar.Close > bar.Open

    def IsBearishPinBar(self, bar):
        body = abs(bar.Close - bar.Open)
        upper_wick = bar.High - max(bar.Open, bar.Close)
        lower_wick = min(bar.Open, bar.Close) - bar.Low
        return upper_wick > 2 * body and lower_wick < body and bar.Close < bar.Open

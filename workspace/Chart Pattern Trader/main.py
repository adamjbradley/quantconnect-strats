from AlgorithmImports import *

# Import detectors
from detectors.head_and_shoulders import HeadAndShouldersDetector
from detectors.inverse_head_and_shoulders import InverseHeadAndShouldersDetector
from detectors.double_top import DoubleTopDetector
from detectors.double_bottom import DoubleBottomDetector
from detectors.cup_and_handle import CupAndHandleDetector
from detectors.ascending_triangle import AscendingTriangleDetector
from detectors.descending_triangle import DescendingTriangleDetector
from detectors.symmetrical_triangle import SymmetricalTriangleDetector
from detectors.rectangle import RectangleDetector
from detectors.flag import FlagDetector

class MultiPatternChartDetectionAlgorithm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(100000)

        self.sigma = int(self.GetParameter("smoothing_sigma"))
        self.max_position_pct = float(self.GetParameter("max_position_pct"))

        self.num_stocks = 1000
        self.window_size = 30
        self.atr_period = 14

        self.detectors = {}         # {symbol: [detectors]}
        self.entries = {}           # {symbol: (entry_price, pattern_name, atr_value)}
        self.atr_indicators = {}    # {symbol: ATR indicator}
        self.pattern_stats = {}     # {pattern: {trades, wins, losses, total_pnl}}

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction)

        # ✅ Log key parameters
        self.Debug(f"PARAMETERS:")
        self.Debug(f"  Start Date: {self.StartDate}")
        self.Debug(f"  End Date: {self.EndDate}")
        self.Debug(f"  Cash: ${self.Portfolio.Cash:,.2f}")
        self.Debug(f"  Max Position %: {self.max_position_pct:.2%}")
        self.Debug(f"  ATR Period: {self.atr_period}")
        self.Debug(f"  Window Size: {self.window_size}")
        self.Debug(f"  Smoothing Sigma: 2")

        # Detector summary
        detector_classes = [
            HeadAndShouldersDetector,
            InverseHeadAndShouldersDetector,
            DoubleTopDetector,
            DoubleBottomDetector,
            CupAndHandleDetector,
            AscendingTriangleDetector,
            DescendingTriangleDetector,
            SymmetricalTriangleDetector,
            RectangleDetector,
            FlagDetector
        ]

        self.Debug(f"DETECTORS ENABLED:")
        detector_names = []
        for cls in detector_classes:
            name = cls.__name__.replace("Detector", "")
            direction = cls().direction()
            detector_names.append(f"{name} ({direction})")
            self.Debug(f"  {name:25} → {direction.upper()}")

        # Visual annotation on chart
        desc = f"Detectors: {len(detector_classes)} | Window: {self.window_size} | Sigma: 2 | MaxPos: {self.max_position_pct:.2%}"
        self.Plot("Parameters", "Setup", 1)
        self.Debug(f"[Summary] {desc}")

    def CoarseSelectionFunction(self, coarse):
        selected = sorted(
            [x for x in coarse if x.HasFundamentalData],
            key=lambda x: x.DollarVolume,
            reverse=True
        )
        return [x.Symbol for x in selected]

    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            symbol = security.Symbol

            # Add pattern detectors
            self.detectors[symbol] = [
                #HeadAndShouldersDetector(self.window_size, smoothing_sigma=self.sigma),
                #InverseHeadAndShouldersDetector(self.window_size),
                DoubleTopDetector(self.window_size, smoothing_sigma=self.sigma),
                #DoubleBottomDetector(self.window_size),
                #CupAndHandleDetector(self.window_size),
                AscendingTriangleDetector(self.window_size),
                #DescendingTriangleDetector(self.window_size),
                #SymmetricalTriangleDetector(self.window_size),
                #RectangleDetector(self.window_size),
                #FlagDetector(self.window_size)
            ]

            # Add ATR indicator
            self.atr_indicators[symbol] = self.ATR(symbol, self.atr_period, Resolution.Daily)

        for security in changes.RemovedSecurities:
            symbol = security.Symbol
            self.detectors.pop(symbol, None)
            self.entries.pop(symbol, None)
            self.atr_indicators.pop(symbol, None)

    def OnData(self, data: Slice):
        for symbol in list(self.detectors.keys()):
            if symbol not in data or not data[symbol]:
                continue

            price = float(data[symbol].Close)
            atr = self.atr_indicators[symbol]
            if not atr.IsReady:
                continue

            # Manage open position
            if symbol in self.entries and self.Portfolio[symbol].Invested:
                entry_price, pattern_name, entry_atr = self.entries[symbol]
                stop = entry_price - 2.5 * entry_atr
                target = entry_price + 1.0 * entry_atr

                if price <= stop:
                    self.Debug(f"{self.Time.date()} | {symbol} STOP LOSS ({pattern_name}) at {price:.2f}")
                    self.Liquidate(symbol)
                    self.update_pattern_stats(pattern_name, (price - entry_price) / entry_price)
                    self.entries.pop(symbol)
                    continue

                elif price >= target:
                    self.Debug(f"{self.Time.date()} | {symbol} TAKE PROFIT ({pattern_name}) at {price:.2f}")
                    self.Liquidate(symbol)
                    self.update_pattern_stats(pattern_name, (price - entry_price) / entry_price)
                    self.entries.pop(symbol)
                    continue

            # Evaluate new pattern signals
            for detector in self.detectors[symbol]:
                detector.update(price)
                if detector.detect() and not self.Portfolio[symbol].Invested:
                    pattern_name = detector.name()
                    direction = detector.direction()
                    self.Debug(f"{self.Time.date()} | {pattern_name} detected on {symbol} ({direction})")

                    position_size = self.Portfolio.Cash * self.max_position_pct
                    quantity = int(position_size / price)
                    if quantity > 0:
                        if direction == "long":
                            self.MarketOrder(symbol, quantity)
                        else:
                            self.MarketOrder(symbol, -quantity)
                        self.entries[symbol] = (price, pattern_name, atr.Current.Value)
                    break

    def update_pattern_stats(self, pattern, pnl):
        if pattern not in self.pattern_stats:
            self.pattern_stats[pattern] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "trades": 0}

        stats = self.pattern_stats[pattern]
        stats["trades"] += 1
        stats["total_pnl"] += pnl
        if pnl > 0:
            stats["wins"] += 1
        else:
            stats["losses"] += 1

        # Live plot win rate and PnL
        win_rate = stats["wins"] / stats["trades"]
        avg_pnl = stats["total_pnl"] / stats["trades"]
        self.Plot("Pattern Stats", f"{pattern}_WinRate", win_rate * 100)
        self.Plot("Pattern Stats", f"{pattern}_AvgPnL", avg_pnl * 100)

    def OnEndOfAlgorithm(self):
        self.Debug("Pattern performance summary:")
        for pattern, stats in self.pattern_stats.items():
            win_rate = stats["wins"] / stats["trades"]
            avg_pnl = stats["total_pnl"] / stats["trades"]
            self.Debug(f"{pattern}: Trades={stats['trades']}, WinRate={win_rate:.2%}, AvgPnL={avg_pnl:.2%}")

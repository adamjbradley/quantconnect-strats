from AlgorithmImports import *
from symbol_data import SymbolData
from utils import get_market_cap_thresholds, get_sector_name_to_code

class ROCReboundStrategy(QCAlgorithm):
    def Initialize(self):
        # Set the start and end dates for the backtest
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2027, 1, 1)
        self.set_cash(100000)

        # Add SPY as the benchmark
        self.add_equity("SPY", Resolution.DAILY)
        self.set_benchmark("SPY")

        # Add VIX data
        self.vix = self.add_data(CBOE, "VIX", Resolution.DAILY).Symbol

        # Create a custom chart
        vix_chart = Chart("VIX Chart")
        self.add_chart(vix_chart)
        vix_chart.add_series(Series("VIX Close", SeriesType.LINE))
        
        # Retrieve parameters
        cap_tiers_param = self.get_parameter("capTiers") or "micro, small, mid"
        self.cap_tiers = [x.strip().lower() for x in cap_tiers_param.split(",")]

        sector_tiers_param = self.get_parameter("sectorTiers") or "technology"
        self.sector_tiers = [x.strip().lower() for x in sector_tiers_param.split(",")]

        self.volume_surge_threshold = float(self.get_parameter("volumeSurgeThreshold") or 0.5)
        self.vix_threshold = float(self.get_parameter("vixThreshold") or 1000)
        self.roc_min = float(self.get_parameter("rocMin") or -30)
        self.roc_max = float(self.get_parameter("rocMax") or -15)
        self.lookback = int(self.GetParameter("lookback") or 14)
        self.volume_window = int(self.GetParameter("volume_window") or 14)
        self.max_holding_days = int(self.GetParameter("max_holding_days") or 15)
        self.trade_allocation_pct = float(self.GetParameter("trade_allocation_pct") or 0.01)
        self.atr_stop_loss_multiplier = float(self.GetParameter("atr_stop_loss_multiplier") or 2.5)
        self.atr_take_profit_multiplier = float(self.GetParameter("atr_take_profit_multiplier") or 1.0)

        # Log parameters
        self.custom_log(f"Parameter: capTiers = {cap_tiers_param}", level="debug")
        self.custom_log(f"Parameter: sectorTiers = {sector_tiers_param}", level="debug")
        self.custom_log(f"Parameter: volumeSurgeThreshold = {self.volume_surge_threshold}", level="debug")
        self.custom_log(f"Parameter: vixThreshold = {self.vix_threshold}", level="debug")
        self.custom_log(f"Parameter: rocMin = {self.roc_min}", level="debug")
        self.custom_log(f"Parameter: rocMax = {self.roc_max}", level="debug")
        self.custom_log(f"Parameter: lookback: {self.lookback}", level="debug")
        self.custom_log(f"Parameter: volume_window: {self.volume_window}", level="debug")
        self.custom_log(f"Parameter: max_holding_days: {self.max_holding_days}", level="debug")
        self.custom_log(f"Parameter: trade_allocation_pct: {self.trade_allocation_pct}", level="debug")
        self.daily_change_log_threshold = float(self.get_parameter("log_gain_loss_threshold") or 0.02)  # 2%

        # Load market cap thresholds and sector codes from utils
        self.market_cap_thresholds = get_market_cap_thresholds()
        sector_name_to_code = get_sector_name_to_code()
        self.sector_codes = [sector_name_to_code[name] for name in self.sector_tiers if name in sector_name_to_code]
       
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.symbol_data = {}
        self.to_buy = {}  # {symbol: signal_date}
        self.open_positions = {}  # {symbol: {entry, target, stop, entry_date}}

        self.max_daily_loss_pct = float(self.GetParameter("max_daily_loss_pct") or 0.01)

        # Variables to track daily loss
        self.starting_portfolio_value = self.Portfolio.TotalPortfolioValue
        self.trading_halted_today = False

        # Schedule a function to reset daily tracking variables at market open
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.ResetDailyLossTracking)
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.BeforeMarketClose("SPY", 1), self.LogDailyChangeContext)

        self.spy = self.AddEquity("SPY", Resolution.DAILY).Symbol
        self.donchian = self.DCH(self.spy, 20, 20, Resolution.DAILY)
        self.Plot("Donchian Channel", "Upper Band", self.donchian.UpperBand.Current.Value)
        self.Plot("Donchian Channel", "Lower Band", self.donchian.LowerBand.Current.Value)

        
        self.daily_starting_value = self.Portfolio.TotalPortfolioValue

        self.set_warm_up(self.lookback + self.volume_window, Resolution.DAILY)

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
        if self.is_warming_up:    
            return

        # Close existing trades
        for symbol, pos in list(self.open_positions.items()):
            price = self.securities[symbol].price
            target = pos["target"]
            stop = pos["stop"]

            if price >= target or price <= stop:
                self.liquidate(symbol)
                self.open_positions.pop(symbol)
            else:
                holding_days = (self.time.date() - pos["entry_date"]).days
                if holding_days > self.max_holding_days:
                    self.liquidate(symbol)
                    self.open_positions.pop(symbol)

        # Calculate current loss
        current_value = self.Portfolio.TotalPortfolioValue
        loss = self.starting_portfolio_value - current_value
        loss_pct = loss / self.starting_portfolio_value

        # If loss exceeds maximum allowed, liquidate and halt trading
        if loss_pct >= self.max_daily_loss_pct:
            self.Liquidate()
            self.trading_halted_today = True
            self.Debug(f"Maximum daily loss exceeded: {loss_pct:.2%}. Trading halted for the day.")
            #return

        # Check if trading is halted for the day
        if self.trading_halted_today:
            self.Debug(f"Halted today!")
            #return

        # Check for market uptrend
        if not self.IsMarketUptrend():
            self.Debug(f"Market in a downwards trend!")
            return  # Skip trading if the market is not in an uptrend

        # Check VIX level
        if self.vix in data and data[self.vix] is not None:
            current_vix = data[self.vix].Close            
            self.plot("Chart Name", "Series Name", current_vix)
            if current_vix > self.vix_threshold:
                self.custom_log(f"High VIX: {current_vix}", "info")
                return  # Skip trading in high volatility

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

                # Apply ROC range filter
                deep_drop = self.roc_min <= roc_today <= self.roc_max
                volume_surge = current_volume >= self.volume_surge_threshold * avg_volume

                if deep_drop and roc_today > roc_3days_ago and roc_today > roc_yesterday and volume_surge:
                    if not self.portfolio[symbol].invested and symbol not in self.to_buy and symbol not in self.open_positions:
                        self.to_buy[symbol] = self.time.date()

        for symbol, signal_date in list(self.to_buy.items()):
            if self.time.date() <= signal_date:
                continue

            if not self.portfolio[symbol].invested and self.securities[symbol].is_tradable:
                price = self.securities[symbol].price
                if price is None or price <= 0:
                    self.to_buy.pop(symbol)
                    continue

                available_cash = self.portfolio.cash
                max_alloc_cash = available_cash * self.trade_allocation_pct
                quantity = int(max_alloc_cash / price)

                if quantity <= 0:
                    self.to_buy.pop(symbol)
                    continue

                try:
                    ticket = self.market_order(symbol, quantity)
                    self.Debug(f"Placed order for {symbol}: {quantity} shares — Order ID: {ticket.OrderId}")
                except Exception as e:
                    self.custom_log(f"Order failed for {symbol.Value}: {e}")
                finally:
                    self.to_buy.pop(symbol)

    def OnOrderEvent(self, order_event: OrderEvent):
        if order_event.Direction != OrderDirection.Buy:
            return

        if order_event.Status not in [OrderStatus.Filled, OrderStatus.PartiallyFilled]:
            return

        symbol = order_event.Symbol
        price = order_event.FillPrice
        atr = self.symbol_data[symbol].atr

        if not atr.IsReady:
            self.Debug(f"ATR not ready for {symbol}")
            return

        atr_val = atr.Current.Value
        target = price + self.atr_take_profit_multiplier * atr_val
        stop = price - self.atr_stop_loss_multiplier * atr_val

        self.open_positions[symbol] = {
            "entry": price,
            "target": target,
            "stop": stop,
            "entry_date": self.Time.date()
        }
        
    def ResetDailyLossTracking(self):
        self.starting_portfolio_value = self.Portfolio.TotalPortfolioValue
        self.daily_starting_value = self.Portfolio.TotalPortfolioValue
        self.trading_halted_today = False

    def on_end_of_algorithm(self) -> None:
        self.Debug("Running final liquidation of all open positions...")
        for symbol, holding in self.Portfolio.items():
            if holding.Invested and self.Securities[symbol].IsTradable:
                self.Liquidate(symbol)
                self.Debug(f"Liquidated {symbol}")
            elif holding.Invested:
                self.Debug(f"Could NOT liquidate {symbol} (not tradable)")

    # Track when remaining margin is low.
    def on_margin_call_warning(self) -> None:
        self.log("Margin call warning, 5% margin remaining")

    # Review and adjust liquidation orders in response to a margin call.
    def on_margin_call(self, requests) -> list[SubmitOrderRequest]: 
        # Modify order requests to choose what to liquidate.
        return requests        

    def IsMarketUptrend(self):
        if not self.donchian.IsReady:
            return False
        spy_price = self.Securities[self.spy].Price
        middle_band = (self.donchian.UpperBand.Current.Value + self.donchian.LowerBand.Current.Value) / 2
        return spy_price > middle_band

    def LogDailyChangeContext(self):
        end_value = self.Portfolio.TotalPortfolioValue
        change_pct = (end_value - self.daily_starting_value) / self.daily_starting_value

        if abs(change_pct) >= self.daily_change_log_threshold:
            vix = self.Securities[self.vix].Price if self.Securities.ContainsKey(self.vix) else "N/A"
            upper = self.donchian.UpperBand.Current.Value if self.donchian.UpperBand.IsReady else "N/A"
            lower = self.donchian.LowerBand.Current.Value if self.donchian.LowerBand.IsReady else "N/A"
            middle = (upper + lower) / 2 if upper != "N/A" and lower != "N/A" else "N/A"
            spy_price = self.Securities[self.spy].Price if self.Securities.ContainsKey(self.spy) else "N/A"
            trend = self.IsMarketUptrend()

            self.custom_log(
                f"[{self.Time.date()}] Large {'GAIN' if change_pct > 0 else 'LOSS'}: {change_pct:.2%} | "
                f"VIX: {vix} | SPY: {spy_price} | Donchian U: {upper}, L: {lower}, M: {middle} | Uptrend: {trend}",
                level="info"
            )

    def custom_log(self, message, level="info"):
        """
        Custom logging method to handle different log levels.
        Levels: 'debug', 'info', 'error'
        """
        if level == "debug":
            self.debug(message)
        elif level == "info":
            self.log(message)
        elif level == "error":
            self.error(message)
        else:
            self.log(message)  # Default to info level


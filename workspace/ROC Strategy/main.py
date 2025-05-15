from AlgorithmImports import *
from symbol_data import SymbolData
from utils import get_market_cap_thresholds, get_sector_name_to_code, str_to_bool
from ETFConstituentsUniverseSelectionModel import ETFConstituentsUniverseSelectionModel
from logger import LoggerMixin
from fee_model import *
from slippage_model import *

class ROCReboundStrategy(QCAlgorithm):
    def Initialize(self):
        # Set the start and end dates for the backtest
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100000)

        self.logger = LoggerMixin(self)
        self.logger.log("Logger initialized", level="debug")

        # Add SPY as the benchmark
        self.add_equity("SPY", Resolution.DAILY)
        self.set_benchmark("SPY")

        # Add VIX data
        self.vix = self.add_data(CBOE, "VIX", Resolution.DAILY).Symbol

        # Custom chart to track VIX
        vix_chart = Chart("VIX Chart")
        self.add_chart(vix_chart)
        vix_chart.add_series(Series("VIX Close", SeriesType.LINE))

        # Custom chart to visualize VIX at entry vs. trade PnL
        self.trade_index = 0
        self.AddChart(Chart("VIX and Trade PnL"))
        self.Plot("VIX and Trade PnL", "VIX", 0)
        self.Plot("VIX and Trade PnL", "PnL", 0)

        # Retrieve parameters
        cap_tiers = self.get_parameter("cap_tiers") or ""
        self.cap_tiers = [x.strip().lower() for x in cap_tiers.split(",")]

        sector_tiers = self.get_parameter("sector_tiers") or ""
        self.sector_tiers = [x.strip().lower() for x in sector_tiers.split(",")]

        exchange_param = self.get_parameter("exchange_filter") or ""
        self.exchange_filters = [x.strip().upper() for x in exchange_param.split(",")]

        self.enable_volume_surge = self.get_parameter("enable_volume_surge") or "False"
        self.volume_surge_threshold = float(self.get_parameter("volume_surge_threshold") or 0.5)

        self.vix_threshold = float(self.get_parameter("vix_threshold") or 25)
        self.roc_min = float(self.get_parameter("roc_min") or -30)
        self.roc_max = float(self.get_parameter("roc_max") or -15)
        self.roc_lookback = int(self.get_parameter("roc_lookback") or 14)
        self.volume_window = int(self.get_parameter("volume_window") or 14)
        self.max_holding_days = int(self.get_parameter("max_holding_days") or 15)
        self.trade_allocation_pct = float(self.get_parameter("trade_allocation_pct") or 0.1)
        self.atr_stop_loss_multiplier = float(self.get_parameter("atr_stop_loss_multiplier") or 2.5)
        self.atr_take_profit_multiplier = float(self.get_parameter("atr_take_profit_multiplier") or 1.0)

        self.max_open_positions = int(self.get_parameter("max_open_positions") or 10)
        self.max_daily_loss_pct = float(self.get_parameter("max_daily_loss_pct") or 0.01)
        self.universe_mode = self.get_parameter("universe_mode") or "etf"  # Options: "etf" or "top1000"
        self.etf_symbol = self.get_parameter("etf_symbol") or "SPY"
        self.min_open_positions_cap = int(self.get_parameter("min_open_positions_cap") or 5)
        self.max_open_positions_cap = int(self.get_parameter("max_open_positions_cap") or 10)
        self.volatility_scaling_enabled = self.get_parameter("volatility_scaling_enabled") or "True"   
        self.slippage_percent = float(self.get_parameter("slippage_percent") or 0.001)
        self.enable_daily_rebalance = self.get_parameter("enable_daily_rebalance") or "False"
        self.allow_forced_liquidation = self.get_parameter("allow_forced_liquidation") or "True"

        # Log parameters
        self.logger.log(f"Parameter: cap_tiers = {cap_tiers}", level="info")
        self.logger.log(f"Parameter: sector_tiers = {sector_tiers}", level="info")
        self.logger.log(f"Parameter: exchange_filters = {self.exchange_filters}", level="info")
        self.logger.log(f"Parameter: enable_volume_surge = {self.enable_volume_surge}", level="info")        
        self.logger.log(f"Parameter: volumeSurgeThreshold = {self.volume_surge_threshold}", level="info")
        self.logger.log(f"Parameter: vixThreshold = {self.vix_threshold}", level="info")
        self.logger.log(f"Parameter: rocMin = {self.roc_min}", level="info")
        self.logger.log(f"Parameter: rocMax = {self.roc_max}", level="info")
        self.logger.log(f"Parameter: roc_lookback: {self.roc_lookback}", level="info")
        self.logger.log(f"Parameter: volume_window: {self.volume_window}", level="info")
        self.logger.log(f"Parameter: max_holding_days: {self.max_holding_days}", level="info")
        self.logger.log(f"Parameter: trade_allocation_pct: {self.trade_allocation_pct}", level="info")
        self.logger.log(f"Parameter: atr_stop_loss_multiplier: {self.atr_stop_loss_multiplier}", level="info")
        self.logger.log(f"Parameter: atr_take_profit_multiplier: {self.atr_take_profit_multiplier}", level="info")
        self.logger.log(f"Parameter: max_open_positions: {self.max_open_positions}", level="info")
        self.logger.log(f"Parameter: max_daily_loss_pct = {self.max_daily_loss_pct}", level="info")
        self.logger.log(f"Parameter: universe_mode = {self.universe_mode}", level="info")
        self.logger.log(f"Parameter: etf_symbol = {self.etf_symbol}", level="info")
        self.logger.log(f"Parameter: min_open_positions_cap = {self.min_open_positions_cap}", level="info")
        self.logger.log(f"Parameter: max_open_positions_cap = {self.max_open_positions_cap}", level="info")
        self.logger.log(f"Parameter: volatility_scaling_enabled = {self.volatility_scaling_enabled}", level="info")
        self.logger.log(f"Parameter: slippage_percent = {self.slippage_percent}", level="info")
        self.logger.log(f"Parameter: enable_daily_rebalance = {self.enable_daily_rebalance}", level="info")
        self.logger.log(f"Parameter: allow_forced_liquidation = {self.allow_forced_liquidation}", level="info")

        # Load market cap thresholds and sector codes from utils
        self.market_cap_thresholds = get_market_cap_thresholds()
        sector_name_to_code = get_sector_name_to_code()
        self.sector_codes = [sector_name_to_code[name] for name in self.sector_tiers if name in sector_name_to_code]
       
        # Universe related matters
        self.universe_settings.resolution = Resolution.DAILY
        if self.universe_mode == "etf":
            self.AddUniverseSelection(ETFConstituentsUniverseSelectionModel(self.etf_symbol, self.universe_settings, self._etf_constituents_filter))
        else:
            self.add_universe(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.symbol_data = {}
        self.to_buy = {}  # {symbol: signal_date}
        self.open_positions = {}  # {symbol: {entry, target, stop, entry_date}}
        self.etf_constituents = set()

        # Variables to track daily loss
        self.starting_portfolio_value = self.Portfolio.TotalPortfolioValue
        self.trading_halted_today = False

        # Schedule a function to reset daily tracking variables at market open
        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 1), self.ResetDailyLossTracking)

        if self.enable_daily_rebalance:
            # Schedule a function to rebalance max open positions daily
            self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen("SPY", 5), self.RebalanceMaxOpenPositions)

        self.set_warm_up(self.roc_lookback + self.volume_window, Resolution.DAILY)

    def CoarseSelectionFunction(self, coarse):
        # Filter for securities with fundamental data
        return [x.Symbol for x in coarse if x.HasFundamentalData]

    def FineSelectionFunction(self, fine):
        selected = []

        for stock in fine:
            # Defensive checks
            if not stock.CompanyReference or not stock.AssetClassification:
                continue

            market_cap = stock.MarketCap
            sector_code = stock.AssetClassification.MorningstarSectorCode
            exchange = stock.CompanyReference.PrimaryExchangeID

            # Exchange filter — only apply if filters are provided
            if self.exchange_filters and exchange not in self.exchange_filters:
                continue

            # Market cap filter — only apply if tiers are set
            cap_match = True
            if self.cap_tiers:
                cap_match = any(
                    self.market_cap_thresholds[tier][0] <= market_cap <= self.market_cap_thresholds[tier][1]
                    for tier in self.cap_tiers
                    if tier in self.market_cap_thresholds
                )

            # Sector filter — only apply if sector codes are set
            sector_match = True
            if self.sector_codes:
                sector_match = sector_code in self.sector_codes

            # ✅ New: Only keep stocks with positive earnings or positive ROE
            eps_12m = stock.EarningReports.BasicEPS.TwelveMonths
            roe = stock.OperationRatios.ROE.Value
            fundamental_match = (eps_12m is not None and eps_12m > 0) or (roe is not None and roe > 0)

            # Low Debt-to-Equity
            debt_equity = stock.OperationRatios.TotalDebtEquityRatio.Value
            has_low_debt = debt_equity is not None and debt_equity <= 1.0  # Threshold can be parameterize

            if cap_match and sector_match:
                selected.append(stock.Symbol)

        return selected

    def _etf_constituents_filter(self, constituents: list[ETFConstituentUniverse]) -> list[Symbol]:
        # Select all Equities in the ETF.
        selected = sorted(
            [c for c in constituents if c.weight],
            key=lambda c: c.weight, reverse=True
        )
        return [c.symbol for c in selected]

    def on_data(self, data):
        if self.is_warming_up:    
            return

        # Manage trade exits
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

        # Check if trading is halted for the day
        if self.trading_halted_today:
            return

        # Calculate current loss
        current_value = self.Portfolio.TotalPortfolioValue
        loss = self.starting_portfolio_value - current_value
        loss_pct = loss / self.starting_portfolio_value

        # If loss exceeds maximum allowed, liquidate and halt trading
        if loss_pct >= self.max_daily_loss_pct:
            self.Liquidate()
            self.trading_halted_today = True
            self.logger.log(f"Maximum daily loss exceeded: {loss_pct:.2%}. Trading halted for the day.", level="debug")
            return

        # Check VIX level
        if self.vix in data and data[self.vix] is not None:
            current_vix = data[self.vix].Close            
            self.plot("VIX Chart", "VIX Close", current_vix)
            if current_vix > self.vix_threshold:                
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

                # Apply Volume surge filter                
                volume_surge_enabled = self.enable_volume_surge.lower() == "true"
                passes_volume_surge = True if not volume_surge_enabled else current_volume >= self.volume_surge_threshold * avg_volume

                # ROC Strategy!
                if deep_drop and roc_today > roc_3days_ago and roc_today > roc_yesterday and passes_volume_surge:
                    if not self.portfolio[symbol].invested and symbol not in self.to_buy and symbol not in self.open_positions:
                        self.to_buy[symbol] = self.Time.date()

        for symbol, signal_date in list(self.to_buy.items()):
            if self.time.date() <= signal_date:
                continue

            if (not self.portfolio[symbol].invested and 
                self.securities[symbol].is_tradable and 
                len(self.open_positions) < self.max_open_positions):
                                
                price = self.securities[symbol].price
                if price is None or price <= 0:
                    self.to_buy.pop(symbol)
                    continue

                # Ask the margin model how much buying power is available                
                price = self.Securities[symbol].Price
                quantity = self.CalculateOrderQuantity(symbol, self.trade_allocation_pct)               

                if quantity <= 0:
                    self.logger.log(f"Skipping {symbol.Value}: insufficient buying power {price:.2f})", level="warn")
                    self.to_buy.pop(symbol)
                    continue

                try:
                    self.market_order(symbol, quantity)
                except Exception as e:
                    self.logger.log(f"Order failed for {symbol.Value}: {e}")
                finally:
                    self.to_buy.pop(symbol)
            else:
                if len(self.open_positions) >= self.max_open_positions:
                    self.logger.log(f"Max open positions reached. Skipping {symbol}", level="debug")
                    continue

    def on_splits(self, splits: Splits):
        for symbol, split in splits.items():
            if split.Type == 0:
                # Early warning signal — no action yet
                self.logger.log(f"[SPLIT WARNING] {symbol.Value} will split soon.", level="debug")
            
            elif split.Type == 1:
                split_ratio = split.SplitFactor
                if split_ratio > 1:
                    # FORWARD SPLIT (e.g., 2-for-1 → ratio = 2.0)
                    self.logger.log(f"[FORWARD SPLIT] {symbol.Value} split {split_ratio:.2f}-for-1. Considering hold/entry.", level="debug")

                    # Optional: delay re-entry logic if just added to universe
                    if symbol in self.to_buy:
                        self.logger.log(f"Delaying trade for {symbol.Value} due to split adjustment.", level="debug")
                        self.to_buy.pop(symbol)

                elif 0 < split_ratio < 1:
                    # REVERSE SPLIT (e.g., 1-for-10 → ratio = 0.1)
                    self.logger.log(f"[REVERSE SPLIT] {symbol.Value} reverse split at ratio {split_ratio:.2f}. Liquidating to avoid exposure.", level="debug")
                    self.Liquidate(symbol)
                    if symbol in self.open_positions:
                        self.open_positions.pop(symbol, None)

                else:
                    self.logger.log(f"[UNKNOWN SPLIT] {symbol.Value} with factor {split_ratio}. Manual review recommended.", level="error")
                    
    def on_delistings(self, delistings: Delistings) -> None:
        for symbol, delisting in delistings.items():
            self.logger.log(f"{self.Time}: Delisting event for {symbol} - Type: {delisting.Type}, Time: {delisting.Time}", level="debug")
            if self.Portfolio[symbol].Invested:
                self.Liquidate(symbol, "Delisting Event")
            self.symbol_data.pop(symbol, None)
            self.open_positions.pop(symbol, None) 
                   
    def on_securities_changed(self, changes: SecurityChanges) -> None:
        # Iterate through the added securities
        for security in changes.AddedSecurities:
            self.logger.log(f"{self.Time}: Added {security.Symbol}", level="debug")
            
            security.SetFeeModel(CustomFeeModel())
            security.SetSlippageModel(CustomSlippageModel(slippage_percent=self.slippage_percent))

            # Optional: initialize symbol data if not already added
            if security.Symbol not in self.symbol_data:
                self.symbol_data[security.Symbol] = SymbolData(self, security.Symbol, self.roc_lookback, self.volume_window)

        # Iterate through the removed securities
        for security in changes.RemovedSecurities:
            #self.Debug(f"{self.Time}: Removed {security.Symbol}")
            if self.Portfolio[security.Symbol].Invested:
                self.Liquidate(security.Symbol)
            # Clean up tracking dictionaries
            self.symbol_data.pop(security.Symbol, None)
            self.open_positions.pop(security.Symbol, None)
            
    def on_order_event(self, order_event: OrderEvent):
        symbol = order_event.Symbol
        status = order_event.Status
        direction = order_event.Direction
        order_id = order_event.OrderId

        if status == OrderStatus.Filled:
            if direction == OrderDirection.Buy:
                price = order_event.FillPrice
                if symbol not in self.symbol_data:
                    self.logger.log(f"Filled BUY for unknown symbol: {symbol}", level="warn")
                    return

                atr = self.symbol_data[symbol].atr
                if not atr.IsReady:
                    return

                atr_val = atr.Current.Value
                target = price + self.atr_take_profit_multiplier * atr_val
                stop = price - self.atr_stop_loss_multiplier * atr_val
                vix_entry = self.Securities[self.vix].Price

                self.open_positions[symbol] = {
                    "entry": price,
                    "target": target,
                    "stop": stop,
                    "vix_entry": vix_entry,
                    "entry_date": self.Time.date()
                }
                self.logger.log(f"Order {order_id}: BUY filled for {symbol.Value} at {price:.2f}", level="debug")

            elif direction == OrderDirection.Sell:
                if symbol in self.open_positions:
                    self.logger.log(f"Order {order_id}: SELL filled for {symbol.Value}", level="debug")
                    
                    entry_info = self.open_positions.pop(symbol, None)
                    if entry_info:
                        vix_entry = entry_info.get("vix_entry")
                        pnl = order_event.FillPrice - entry_info["entry"]
                        self.Plot("VIX and Trade PnL", "VIX", vix_entry)
                        self.Plot("VIX and Trade PnL", "PnL", pnl)
                        self.trade_index += 1

            elif status == OrderStatus.PartiallyFilled:
                self.logger.log(f"Order {order_id}: Partially filled for {symbol.Value}", level="info")

            elif status == OrderStatus.Canceled:
                self.logger.log(f"Order {order_id}: Cancelled for {symbol.Value}", level="warning")

            elif status == OrderStatus.Submitted:
                self.logger.log(f"Order {order_id}: Submitted to broker for {symbol.Value}", level="debug")

            elif status == OrderStatus.New:
                self.logger.log(f"Order {order_id}: Created for {symbol.Value}", level="debug")

            elif status == OrderStatus.Invalid:
                self.logger.log(f"Order {order_id}: Invalid order for {symbol.Value}. Message: {order_event.Message}", level="error")

            elif status == OrderStatus.CancelPending:
                self.logger.log(f"Order {order_id}: Cancel pending for {symbol.Value}", level="debug")

            elif status == OrderStatus.UpdateSubmitted:
                self.logger.log(f"Order {order_id}: Update submitted for {symbol.Value}", level="debug")

            else:
                self.logger.log(f"Order {order_id}: Unknown status {status} for {symbol.Value}", level="error")
                
    def on_end_of_algorithm(self):
        self.liquidate()

    # Track when remaining margin is low.
    def on_margin_call_warning(self) -> None:
        self.logger.log("⚠️ Margin Call Warning Triggered!", level="error")
        
        # Optional: start liquidating smallest winners or highest-risk trades
        sorted_by_risk = sorted(
            self.open_positions.items(),
            key=lambda kv: abs(self.Securities[kv[0]].Price - kv[1]['stop'])  # closeness to stop
        )
        for symbol, _ in sorted_by_risk[:3]:  # Just an example: close top 3 risky positions
            self.Liquidate(symbol)
            #self.logger.log(f"Preemptively liquidated {symbol.Value} due to margin risk.")

    # Review and adjust liquidation orders in response to a margin call. Liquidate
    def on_margin_call(self, requests) -> list[SubmitOrderRequest]: 
        self.logger.log("Margin Call Triggered. Liquidating all losing positions.", level="error")

        # Filter requests for symbols with negative unrealized profit
        losing_requests = [
            r for r in requests
            if r.Symbol in self.Portfolio and self.Portfolio[r.Symbol].UnrealizedProfit < 0
        ]

        return losing_requests

    def ResetDailyLossTracking(self):
            self.starting_portfolio_value = self.Portfolio.TotalPortfolioValue
            self.trading_halted_today = False

    def RebalanceMaxOpenPositions(self):
        margin_pct = self.Portfolio.MarginRemaining / self.Portfolio.TotalPortfolioValue if self.Portfolio.TotalPortfolioValue > 0 else 0

        # Base scaling: more margin → more allowed positions
        scaled_by_margin = int(self.min_open_positions_cap + (self.max_open_positions_cap - self.min_open_positions_cap) * margin_pct)

        # Adjust based on VIX regime
        if self.volatility_scaling_enabled and self.vix in self.Securities and self.Securities[self.vix].HasData:
            vix_level = self.Securities[self.vix].Price
            if vix_level > 30:
                volatility_factor = 0.5
            elif vix_level > 20:
                volatility_factor = 0.75
            else:
                volatility_factor = 1.0
            scaled_by_margin = int(scaled_by_margin * volatility_factor)

        # Bound and apply
        new_cap = max(self.min_open_positions_cap, min(scaled_by_margin, self.max_open_positions_cap))
        self.logger.log(f"[{self.Time}] Rebalanced max_open_positions from {self.max_open_positions} to {new_cap}", level="debug")
        self.max_open_positions = new_cap

        # Optional forced liquidation if over capacity
        if len(self.open_positions) > self.max_open_positions:
            excess = len(self.open_positions) - self.max_open_positions
            self.logger.log(f"[{self.Time}] Over max_open_positions. Reducing by closing {excess} positions.", level="debug")

            # Close least profitable positions first
            sorted_positions = sorted(
                self.open_positions.items(),
                key=lambda kv: self.Portfolio[kv[0]].UnrealizedProfit
            )

            # Close least profitable positions first
            if self.allow_forced_liquidation:
                for symbol, _ in sorted_positions[:excess]:
                    self.logger.log(f"[{self.Time}] Closing {symbol.Value} due to cap rebalance", level="debug")
                    self.Liquidate(symbol)
                    self.open_positions.pop(symbol, None)

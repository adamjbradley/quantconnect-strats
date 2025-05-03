from AlgorithmImports import *

class SP500ConstituentStrategy(QCAlgorithm):
    def Initialize(self):
        # Set backtest dates
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 5, 3)  # Today
        self.SetCash(100000)
        
        # Parameters - can be adjusted for optimization
        self.bb_period = self.GetParameter("bb_period", 30)
        self.bb_std_dev = self.GetParameter("bb_std_dev", 2.0)
        self.rsi_threshold = self.GetParameter("rsi_threshold", 30)
        self.bb_width_threshold_daily = self.GetParameter("bb_width_threshold_daily", 0.3)
        self.bb_width_threshold_minute = self.GetParameter("bb_width_threshold_minute", 0.15)
        self.rsi_period = self.GetParameter("rsi_period", 14)
        self.rsi_exit_threshold = self.GetParameter("rsi_exit_threshold", 70)
        self.max_position_size_per_stock = self.GetParameter("max_position_size", 0.1)
        self.max_total_positions = self.GetParameter("max_positions", 10)
        self.atr_period = self.GetParameter("atr_period", 14)
        self.atr_tp_multiplier = self.GetParameter("atr_tp_multiplier", 2.0)
        self.atr_sl_multiplier = self.GetParameter("atr_sl_multiplier", 3.0)
        self.position_timeout_bars = self.GetParameter("position_timeout_bars", 2)
        
        # Set resolution to daily
        self.resolution = Resolution.Daily
        
        # Get indicator periods from parameters
        self.bbperiod = int(self.bb_period)
        self.rsi_period = int(self.rsi_period)
        self.atr_period = int(self.atr_period)
        
        # Warm up period to ensure indicators have enough data
        warmup_period = max(self.bbperiod, self.rsi_period, self.atr_period) + 1
        self.SetWarmup(warmup_period)
        
        # Set benchmark to SPY
        self.SetBenchmark("SPY")
        
        # Subscribe to S&P 500 ETF for universe selection
        self.spy = self.AddEquity("SPY", self.resolution).Symbol
        
        # Create Universe Selection Model
        self.SetUniverseSelection(ETFConstituentsUniverseSelectionModel(self.spy))
        
        # Dictionary to store indicators for each symbol
        self.indicators = {}
        
        # Set thresholds based on resolution
        self.rsi_threshold = float(self.rsi_threshold)
        self.bb_width_threshold = float(self.bb_width_threshold_daily)  # Using daily threshold
        
        # Track state for each symbol
        self.previous_bars = {}
        self.last_red_candles = {}
        self.looking_for_green_confirmation = {}
        self.stop_loss_prices = {}  # Store stop loss prices
        self.take_profit_prices = {}  # Store take profit prices
        self.position_entry_bar_count = {}  # Track bars since entry
        
        # Position management from parameters
        self.max_position_size_per_stock = float(self.max_position_size_per_stock)
        self.max_total_positions = int(self.max_total_positions)
        
        # Logging level configuration
        self.log_level = self.GetParameter("log_level", 1)
        
        # Log parameters for tracking
        self.log(1, f"Strategy Parameters:")
        self.log(1, f"BB Period: {self.bbperiod}, BB Std Dev: {self.bb_std_dev}")
        self.log(1, f"RSI Period: {self.rsi_period}, RSI Threshold: {self.rsi_threshold}")
        self.log(1, f"BB Width Threshold (Daily): {self.bb_width_threshold_daily}")
        self.log(1, f"BB Width Threshold (Minute): {self.bb_width_threshold_minute}")
        self.log(1, f"RSI Exit Threshold: {self.rsi_exit_threshold}")
        self.log(1, f"Max Position Size: {self.max_position_size_per_stock}")
        self.log(1, f"Max Total Positions: {self.max_total_positions}")
        self.log(1, f"ATR Period: {self.atr_period}")
        self.log(1, f"ATR Take Profit Multiplier: {self.atr_tp_multiplier}")
        self.log(1, f"ATR Stop Loss Multiplier: {self.atr_sl_multiplier}")
        self.log(1, f"Log Level: {self.log_level}")
    
    def log(self, level: int, message: str):
        if self.log_level >= level:
            self.Debug(message)
    
    def OnSecuritiesChanged(self, changes):
        # Add indicators for new securities
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            if symbol not in self.indicators:
                # Initialize indicators for daily resolution
                self.indicators[symbol] = {
                    'bb': self.BB(symbol, self.bbperiod, float(self.bb_std_dev), MovingAverageType.Simple, self.resolution),
                    'rsi': self.RSI(symbol, self.rsi_period, MovingAverageType.Simple, self.resolution),
                    'atr': self.ATR(symbol, self.atr_period, MovingAverageType.Simple, self.resolution)
                }
                
                self.previous_bars[symbol] = None
                self.last_red_candles[symbol] = None
                self.looking_for_green_confirmation[symbol] = False
                self.stop_loss_prices[symbol] = None
                self.take_profit_prices[symbol] = None
                self.position_entry_bar_count[symbol] = 0
        
        # Clean up indicators for removed securities
        for security in changes.RemovedSecurities:
            symbol = security.Symbol
            if symbol in self.indicators:
                del self.indicators[symbol]
                del self.previous_bars[symbol]
                del self.last_red_candles[symbol]
                del self.looking_for_green_confirmation[symbol]
                del self.stop_loss_prices[symbol]
                del self.take_profit_prices[symbol]
                del self.position_entry_bar_count[symbol]
    
    def OnData(self, data):
        # Skip trading during warmup period
        if self.IsWarmingUp:
            return
        
        # Check if we have reached maximum positions
        current_positions = 0
        for kvp in self.Portfolio:
            if kvp.Value.Invested:
                current_positions += 1
        
        for symbol in self.indicators:
            if not data.ContainsKey(symbol):
                continue
            
            # Check if indicators are ready for this symbol
            indicators = self.indicators[symbol]
            if not indicators['bb'].IsReady or not indicators['rsi'].IsReady or not indicators['atr'].IsReady:
                continue
            
            if not data.Bars.ContainsKey(symbol):
                continue
                
            current_bar = data.Bars[symbol]
            
            # Skip if we don't have previous bar data
            if self.previous_bars[symbol] is None:
                self.previous_bars[symbol] = current_bar
                continue
            
            previous_bar = self.previous_bars[symbol]
            
            # Get current indicator values
            bb = indicators['bb']
            rsi = indicators['rsi']
            atr = indicators['atr']
            lower_bollinger = bb.LowerBand.Current.Value
            current_rsi = rsi.Current.Value
            current_atr = atr.Current.Value
            
            # Calculate Bollinger Band Width (percentage)
            upper_bollinger = bb.UpperBand.Current.Value
            bb_width = ((upper_bollinger - lower_bollinger) / bb.MiddleBand.Current.Value) * 100
            
            # Check for red candle with low below lower Bollinger Band
            is_red_candle = current_bar.Close < previous_bar.Close
            low_below_bb = current_bar.Low < lower_bollinger
            
            # Debug log to check bar values
            self.log(3, f"{symbol} Bars - Previous Close: {previous_bar.Close:.2f}, Current Close: {current_bar.Close:.2f}")
            
            # Entry Signal - Step 1: Red candle with conditions
            if (is_red_candle and 
                low_below_bb and 
                current_rsi < self.rsi_threshold and 
                bb_width > self.bb_width_threshold):
                
                self.last_red_candles[symbol] = current_bar
                self.looking_for_green_confirmation[symbol] = True
                
                self.log(2, f"{symbol} RED CANDLE SIGNAL | Price: {current_bar.Close:.2f} | " +
                          f"Low: {current_bar.Low:.2f} | BB Lower: {lower_bollinger:.2f} | " +
                          f"RSI: {current_rsi:.2f} | BB Width: {bb_width:.2f} | ATR: {current_atr:.2f}")
                self.log(3, f"{symbol} BB Calc: Upper: {upper_bollinger:.2f} | Middle: {bb.MiddleBand.Current.Value:.2f} | " +
                          f"Std Multiplier: {self.bb_std_dev}")
            
            # Entry Signal - Step 2: Green candle confirmation (Trigger Candle)
            elif (self.looking_for_green_confirmation[symbol] and 
                  self.last_red_candles[symbol] is not None and
                  current_bar.Close > previous_bar.Close and  # Green candle
                  current_bar.Close > self.last_red_candles[symbol].High and  # Closes above previous red high
                  bb_width > self.bb_width_threshold):  # BB width must be above threshold on green candle
                
                # Enter position if we haven't reached max positions
                if not self.Portfolio[symbol].Invested and current_positions < self.max_total_positions:
                    entry_price = current_bar.Close
                    self.SetHoldings(symbol, self.max_position_size_per_stock)
                    current_positions += 1
                    
                    # Use ATR from the trigger (green) candle
                    atr_value = current_atr  # ATR from current (green) candle, not from red candle
                    self.stop_loss_prices[symbol] = entry_price - (float(self.atr_sl_multiplier) * atr_value)
                    self.take_profit_prices[symbol] = entry_price + (float(self.atr_tp_multiplier) * atr_value)
                    self.position_entry_bar_count[symbol] = 0  # Reset bar counter
                    
                    self.log(1, f"{symbol} ENTRY CONFIRMED | Entry: {entry_price:.2f} | " +
                              f"SL: {self.stop_loss_prices[symbol]:.2f} | " +
                              f"TP: {self.take_profit_prices[symbol]:.2f} | " +
                              f"ATR: {atr_value:.2f} | BB Width: {bb_width:.2f}")
                
                # Reset flags
                self.looking_for_green_confirmation[symbol] = False
                self.last_red_candles[symbol] = None
            
            # Reset if we missed the confirmation
            elif self.looking_for_green_confirmation[symbol] and current_bar.Close < previous_bar.Close:
                self.looking_for_green_confirmation[symbol] = False
                self.last_red_candles[symbol] = None
                self.log(3, f"{symbol} Confirmation missed - resetting")
            
            # Exit conditions
            if self.Portfolio[symbol].Invested:
                # Increment bar count for position
                self.position_entry_bar_count[symbol] += 1
                
                # Check timeout condition first
                if self.position_entry_bar_count[symbol] >= int(self.position_timeout_bars):
                    self.Liquidate(symbol)
                    current_positions -= 1
                    self.log(1, f"{symbol} TIMEOUT EXIT | Bars since entry: {self.position_entry_bar_count[symbol]} | " +
                              f"Price: {current_bar.Close:.2f}")
                    self.stop_loss_prices[symbol] = None
                    self.take_profit_prices[symbol] = None
                    self.position_entry_bar_count[symbol] = 0
                
                # Check ATR-based stop loss and take profit
                elif (self.stop_loss_prices[symbol] is not None and 
                    current_bar.Close <= self.stop_loss_prices[symbol]):
                    self.Liquidate(symbol)
                    current_positions -= 1
                    self.log(1, f"{symbol} STOP LOSS HIT | Price: {current_bar.Close:.2f} | " +
                              f"SL: {self.stop_loss_prices[symbol]:.2f}")
                    self.stop_loss_prices[symbol] = None
                    self.take_profit_prices[symbol] = None
                    self.position_entry_bar_count[symbol] = 0
                
                elif (self.take_profit_prices[symbol] is not None and 
                      current_bar.Close >= self.take_profit_prices[symbol]):
                    self.Liquidate(symbol)
                    current_positions -= 1
                    self.log(1, f"{symbol} TAKE PROFIT HIT | Price: {current_bar.Close:.2f} | " +
                              f"TP: {self.take_profit_prices[symbol]:.2f}")
                    self.stop_loss_prices[symbol] = None
                    self.take_profit_prices[symbol] = None
                    self.position_entry_bar_count[symbol] = 0
            
            # Update previous bar for next iteration
            self.previous_bars[symbol] = current_bar
        
        # Log current positions
        self.log(2, f"Current positions: {current_positions}/{self.max_total_positions}")

#region imports
from collections import deque
import math
from AlgorithmImports import *
#endregion

from System import *
from QuantConnect import *
from QuantConnect.Data import *
from QuantConnect.Data.Market import *
from QuantConnect.Data.Consolidators import *
from QuantConnect.Algorithm import *
from QuantConnect.Indicators import *
from QuantConnect.Securities import *
from QuantConnect.Orders import *
from datetime import datetime
from System.Drawing import Color

import decimal as d
import numpy as np

##BB30
#             
class FormalFluorescentYellowArmadillo(QCAlgorithm):

    def Initialize(self):

        self.investment = 10000

        self.SetStartDate(2013, 1, 1)  # Set Start Date
        self.SetEndDate(2023, 12, 31)  # Set End Date
        self.SetCash(self.investment)  # Set Strategy Cash

        '''Initialise the data and resolution required'''
        self.UniverseSettings.Resolution = Resolution.Daily
        # Add QC500 Universe
        self.AddUniverse(self.Universe.QC500)

        # Setting AAPL as our stock of choice and getting the corresponding symbol object
        # EBS, CIO, ORB, SO, WIRE, GENC
        equity_string = "CIO"
        equity = self.AddEquity(equity_string, Resolution.Minute)
        self.symbol = equity.Symbol

        # build a universe using the CoarseFilter and FineFilter functions defined below
        #self.AddUniverse(self.CoarseFilter, self.FineFilter)

        # This is pretty low!
        self.bbandwidth_threshold = 0.03 # 0.15 for 30 minutes | 0.3 for 1 hour
        self.max_trade_intervals = None #intervals
        self.interval_in_seconds = 1800


        # 30 minute consolidators
        # From https://github.com/QuantConnect/Lean/blob/master/Algorithm.Python/DataConsolidationAlgorithm.py
        # define our 30 minute trade bar consolidator. we can
        # access the 30 minute bar from the DataConsolidated events
        thirtyMinuteConsolidator = TradeBarConsolidator(timedelta(minutes=30))

        # attach our event handler. the event handler is a function that will
        # be called each time we produce a new consolidated piece of data.
        thirtyMinuteConsolidator.DataConsolidated += self.ThirtyMinuteBarHandler

        # this call adds our 30 minute consolidator to
        # the manager to receive updates from the engine
        self.SubscriptionManager.AddConsolidator(equity_string, thirtyMinuteConsolidator)
        self.__last = None


        # Bollinger Band Indicator consolidator
        #From https://www.quantconnect.com/forum/discussion/9429/indicator-consolidator-problem/p1
        
        #Bollinger Bands
        # 30 bars
        self.bb = self.BB(self.symbol, 30, 2)

        ##Consolidated
        self.bb_consolidated = BollingerBands(30, 2, MovingAverageType.Simple)

        #Relative Strength Index
        # Last 14 candles
        self.rsi = self.RSI(self.symbol, 14)
        ###Consolidated
        self.rsi_consolidated = RelativeStrengthIndex(14)
                
        #Bollinger Bandwidth
        # (Upper - Lower) / Middle
        self.bbandwidth = 0
        self.bbandwidth_consolidated_value = 0

        #Average True Range
        self.atr = self.ATR(self.symbol, 1, MovingAverageType.Simple)
        self.atr_consolidated = AverageTrueRange(1) 

        ##Consolidated
        ##
        self.ThirtyMinuteTrigger = False
        self.SetWarmUp(30 * 30, Resolution.Minute)     ## Change set warm up

        # State Management
        self.state = 0                

        # Order management
        self.last_order_time = self.UtcTime
        self.quant = 0
        self.order = 0
        self.sl = 0
        self.tp = 0

        self.last_open = 0
        self.last_high = 0
        self.last_low = 0
        self.last_close = 0


        # Consolidated (30 minute timeframe)
        self.last_open_consolidated = 0
        self.last_close_consolidated = 0
        self.last_high_consolidated = 0
        self.last_low_consolidated = 0

        self.open_consolidated = 0
        self.close_consolidated = 0
        self.high_consolidated = 0
        self.low_consolidated = 0

        self.price_consolidated = 0


        

    def OnData(self, data):

        str_format = '%a %b %d %H:%M:%S %Y'
            
        # Buying and Selling don't wait!
        if self.state == 2:
            self.Debug(f"Buying!")

            # 30% risk!
            self.quant = int((self.investment * 0.3) / self.price_consolidated)

            # Buy orders
            ticket = self.MarketOrder(self.symbol, self.quant, tag=self.Time.strftime(str_format))

            # From https://www.quantconnect.com/forum/discussion/1072/setting-a-stop-loss-and-take-profit/p2
            # Should be entry price, not current price!
            tp = self.price_consolidated + (self.atr_consolidated.Current.Price * 1.6)
            stop = self.price_consolidated - (self.atr_consolidated.Current.Price * 1.8)
        
            self.sl = self.StopMarketOrder(self.symbol, -self.quant, stop)
            self.tp = self.LimitOrder(self.symbol, -self.quant, tp)

            self.last_order_time = self.UtcTime

            self.state = 3
            self.Debug(f"{self.Time}: Quantity filled: {ticket.QuantityFilled}; Fill price: {ticket.AverageFillPrice}")
            self.ThirtyMinuteTrigger = False

        if self.state == 3:
            if self.max_trade_intervals != None:
                c = self.UtcTime - self.last_order_time
                if c.seconds > (self.max_trade_intervals * self.interval_in_seconds):
                    self.Debug(f"{self.Time}: Selling! Time since filled: {c.seconds}")
                    self.ClosePosition()
                    self.state = 0
        
        # Only fire every 30 minutes
        if self.ThirtyMinuteTrigger == True:

            if not self.symbol in data:
                return

            if not hasattr(data[self.symbol], "Open"):
                print(f"Symbol {self.symbol} does not have an 'Open' attribute")
                return
        
            # Entry criteria
            # 1. Red candle with low below lower bollinger band
            # 2. RSI is below 25 (red candle)
            # 3. Next candle is green, and close is above the high of the previous red candle            
            # 4. Bollinger Bandwidth ? threshold (0.3 for daily candles, 0.15 for 30 minute candles)
            #
            # The green candle is the tigger candle. Enter at the open of the next candle

            #TP is entry price + 2*ATR of the trigger candle
            #SL is entry price - 3*ATR of the trigger candle            
            
            if self.state == 0:
                if self.low_consolidated < self.bb.LowerBand.Current.Value:
                    if (self.rsi_consolidated.Current.Value) < 25:
                        #self.Debug(f"{self.Time}: Todays close is higher than yesterdays high!")
                        self.Debug(f"{self.Time}: Low has dropped below BB lower band! {self.bb.LowerBand.Current.Value}")
                        self.state = 1
                        return
                    #self.Debug(f"{self.Time}: RSI is above threshold {self.rsi_consolidated}")

                self.state = 0

            elif self.state == 1:
                # Trigger candle!
                if self.close_consolidated > self.last_high_consolidated:
                    self.Debug(f"{self.Time}: 30 Minute BB Bandwidth value {self.bbandwidth_consolidated_value} 30 Minute RSI value {self.rsi_consolidated.Current.Price})")

                    if self.bbandwidth_consolidated_value > self.bbandwidth_threshold:
                        self.Debug(f"{self.Time}: High:{self.high_consolidated}: Low {self.low_consolidated}: Open {self.open_consolidated}: Close {self.close_consolidated}")
                        self.Debug(f"{self.Time}: Last High:{self.last_high_consolidated} Last Low:{self.last_low_consolidated} Last Open {self.last_open_consolidated} Close {self.last_close_consolidated}")

                        self.state = 2
                        return
                    
                    self.Debug(f"{self.Time}: BB bandwidth is not above threshold {self.bbandwidth_consolidated_value}")
            
                self.state = 0
                                
        self.ThirtyMinuteTrigger = False

    def CancelOrders(self):
         # Cancel all open orders
        all_cancelled_orders = self.Transactions.CancelOpenOrders()

    def ClosePosition(self):
        ## Check if we have a long position in the stock
        if self.Portfolio[self.symbol].IsLong:
            # Close the long position
            self.Liquidate(self.symbol)

    def OnOrderEvent(self, orderEvent: OrderEvent) -> None:
        order = self.Transactions.GetOrderById(orderEvent.OrderId)
        # CancelPending 8
        # Canceled = 5
        # Filled = 3
        # Invalid = 7
        # New = 0
        # None = 6
        # PartiallyFilled = 2
        # Submitted = 1
        # UpdateSubmitted = 9
        if orderEvent.Status == OrderStatus.Filled:
            self.Debug(f"{self.Time}: {order.Type}: {orderEvent}")

    def OnAssignmentOrderEvent(self, assignmentEvent: OrderEvent) -> None:
        self.Log(str(assignmentEvent))
        

    def ThirtyMinuteBarHandler(self, sender, bar):
        '''This is our event handler for our 30 minute trade bar defined above in Initialize(). So each time the
        consolidator produces a new 30 minute bar, this function will be called automatically. The 'sender' parameter
        will be the instance of the IDataConsolidator that invoked the event, but you'll almost never need that!'''

        #self.Debug(f"30 Minutes has passed. Time is {self.Time} and state is {self.state}")

        self.ThirtyMinuteTrigger = True

        self.last_open_consolidated = self.open_consolidated
        self.last_close_consolidated = self.close_consolidated
        self.last_high_consolidated = self.high_consolidated
        self.last_low_consolidated = self.low_consolidated
        self.last_price_consolidated = self.price_consolidated
        self.last_bbandwidth_consolidated_value = self.bbandwidth_consolidated_value

        self.open_consolidated = bar.Open
        self.close_consolidated = bar.Close
        self.high_consolidated = bar.High
        self.low_consolidated = bar.Low
        self.price_consolidated = bar.Price

        self.rsi_consolidated.Update(bar.Time,bar.Close)
        self.bb_consolidated.Update(bar.EndTime, bar.Close)
        self.atr_consolidated.Update(bar)
        self.__last = bar
    
        #RSI
        if not self.rsi_consolidated.IsReady:           
            return
    
        #ATR
        if not self.atr_consolidated.IsReady:
            return

        #BB
        if not self.bb_consolidated.IsReady:
            return

        self.bbandwidth_consolidated_value = (self.bb_consolidated.UpperBand.Current.Value - self.bb_consolidated.LowerBand.Current.Value) / self.bb_consolidated.MiddleBand.Current.Value        


    def CoarseFilter(self, universe):
        # filter universe, ensure DollarVolume is above a certain threshold
        # also filter by assets that have fundamental data
        universe = [asset for asset in universe if asset.Price > 1]
        
        # sort universe by highest dollar volume
        sortedByDollarVolume = sorted(universe, key=lambda asset: asset.DollarVolume, reverse=True)
        
        # only select the first 500
        topSortedByDollarVolume = sortedByDollarVolume[:50000]

        # we must return a list of the symbol objects only
        symbolObjects = [asset.Symbol for asset in topSortedByDollarVolume]

        # this line is not necessary, but we will use it for debugging to see a list of ticker symbols
        tickerSymbolValuesOnly = [symbol.Value for symbol in symbolObjects]

        return symbolObjects

    def FineFilter(self, coarseUniverse):
        yesterday = self.Time - timedelta(days=1)
        fineUniverse = [asset.Symbol for asset in coarseUniverse]
        tickerSymbolValuesOnly = [symbol.Value for symbol in fineUniverse]
        return fineUniverse

        

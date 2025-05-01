#region imports
from collections import deque
import math
from AlgorithmImports import *
#endregion

            
class FormalFluorescentYellowArmadillo(QCAlgorithm):

    def Initialize(self):

        self.investment = 10000

        self.SetStartDate(2019, 1, 1)  # Set Start Date
        self.SetEndDate(2023, 12, 31)  # Set End Date
        self.SetCash(self.investment)  # Set Strategy Cash

        # Setting AAPL as our stock of choice and getting the corresponding symbol object
        equity = self.AddEquity("CIO", Resolution.Hour)
        self.symbol = equity.Symbol

        #Relative Strength Index
        # Last 14 candles
        self.rsi = self.RSI(self.symbol, 14)

        #Bollinger Bands
        # 30 bars
        self.bb = self.BB(self.symbol, 30, 2)

        #Bollinger Bandwidth
        # (Upper - Lower) / Middle
        self.bbandwidth = 0

        #Average True Range
        self.atr = self.ATR(self.symbol, 1, MovingAverageType.Simple)


        # State Management
        self.state = 0                

        self.SetWarmUp(30 * 30, Resolution.Minute)     ## Change set warm up

        # Order management
        self.last_order_time = self.UtcTime
        self.quant = 0
        self.order = 0
        self.sl = 0
        self.tp = 0

        self.last_close = 0
        self.last_open = 0

        self.price = 0

    def OnData(self, data):
        if not self.symbol in data:
            return

        if not hasattr(data[self.symbol], "Open"):
            print(f"Symbol {self.symbol} does not have an 'Open' attribute")
            return

        if self.bb.IsReady:
            self.bbandwidth = (self.bb.UpperBand.Current.Value - self.bb.LowerBand.Current.Value) / self.bb.MiddleBand.Current.Value

        if self.rsi.IsReady:
            self.rsi_value = self.rsi.Current.Value

        # Entry criteria
        # 1. Red candle with low below lower bollinger band
        # 2. RSI is below 25 (red candle)
        # 3. Next candle is green, and close is above the high of the previous red candle            
        # 4. Bollinger Bandwidth ? threshold (0.3 for daily candles, 0.15 for 30 minute candles)
        #
        # The green candle is the tigger candle. Enter at the open of the next candle

        #TP is entry price + 2*ATR of the trigger candle
        #SL is entry price - 3*ATR of the trigger candle

        str_format = '%a %b %d %H:%M:%S %Y'
        
        # Only fire every hour (though we do want this to be every 30 minutes!)

        if self.state == 0:
            if data[self.symbol].Close < self.bb.LowerBand.Current.Value:
                if (self.rsi.Current.Value) < 25:
                    self.state = 1

        elif self.state == 1:
            # Entry candle!
            if data[self.symbol].Close > self.last_high:
                if self.bbandwidth > 0.15:
                    self.state = 2

        elif self.state == 2:        
            # 30% risk!
            self.quant = int((self.investment / 3) / self.price)

            # Buy orders
            ticket = self.MarketOrder(self.symbol, self.quant, tag=self.Time.strftime(str_format))

            tp = data[self.symbol].Price + (self.atr.Current.Price * 1.6)
            stop = data[self.symbol].Price - (self.atr.Current.Price * 1.8)

            self.sl = self.StopMarketOrder(self.symbol, -self.quant, stop)  
            self.tp = self.LimitOrder(self.symbol, -self.quant, tp) 

            self.last_order_time = self.UtcTime

            self.state = 3
            self.Debug(f"Quantity filled: {ticket.QuantityFilled}; Fill price: {ticket.AverageFillPrice}")

                
        elif self.state == 3:
            c = self.UtcTime - self.last_order_time
            if c.seconds > (1800 * 2):
                self.Debug(f"Time since filled: {c.seconds}")
                #self.CancelOrders()
                self.ClosePosition()
                self.state = 0
                return

        self.last_open = data[self.symbol].Open
        self.last_close = data[self.symbol].Close
        self.last_high = data[self.symbol].High
        self.price = data[self.symbol].Price

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
        if orderEvent.Status == OrderStatus.Filled:
            self.Debug(f"{self.Time}: {order.Type}: {orderEvent}")

    def OnAssignmentOrderEvent(self, assignmentEvent: OrderEvent) -> None:
        self.Log(str(assignmentEvent))
        
    def GetHistoricalData(self):
        historyData = self.History(self.symbol, 2, Resolution.Hour)
        historyHourlyData = self.History(self.symbol, 24, Resolution.Hour)

        try:
            openDayAfterEarnings = historyData['open'][-1]
            closeDayAfterEarnings = historyData['close'][-1]
            highDayAfterEarnings = historyData['high'][-1]
            closeDayBeforeEarnings = historyData['close'][-2]
        except:
            self.Debug(f"History data unavailable for {symbol.Value}")           

    def SetOrderProperties(self):
        ## you need to replace sl with self.sl, as you want these to be global variables
        ## otherwise, they will not be accessible outside of OnData
        self.sl = self.StopMarketOrder(self.symbol, -self.quant, fxClose - self.slPercent)  
        self.tp = self.LimitOrder(self.symbol, -self.quant, fxClose + self.tpPercent)

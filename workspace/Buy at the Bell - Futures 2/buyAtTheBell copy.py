# region imports
from AlgorithmImports import *
# endregion

class OpeningRangeBreakout(QCAlgorithm):

    quantity = 100
    stopMarketOrderFillTime = datetime.min
    highestSPYPrice = -1
    warmup = False

    ticket = None
    stop_loss = None
    take_profit = None

    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2023, 6, 1)
        self.SetCash(1000000)

        self.instrument = self.AddEquity("QQQ", Resolution.Minute)
        self.instrument.SetDataNormalizationMode(DataNormalizationMode.Raw)

        #Order at the start of the day
        self.Schedule.On(self.DateRules.EveryDay(self.instrument.Symbol), self.TimeRules.AfterMarketOpen(self.instrument.Symbol, 0), self.AtOpeningBell)

        #Close at 10:30
        self.Schedule.On(self.DateRules.EveryDay(self.instrument.Symbol), self.TimeRules.At(10, 30), self.ClosePositions)


    def ClosePositions(self):        
        if self.Portfolio.Invested:
            self.Liquidate()            
        pass

    def OnWarmupFinished(self) -> None:
        self.warmup = True # Done warming up        

    def AtOpeningBell(self) -> None:
        if self.warmup:
            self.Log("Opening Bell!")        
            self.ticket = self.StopMarketOrder(self.instrument.Symbol, self.quantity, 0.98 * self.instrument.Close)

    def OnData(self, data):
        if self.Portfolio.Invested:
            if self.instrument.Close > self.highestSPYPrice:
                self.highestSPYPrice = self.instrument.Close
                updateFields = UpdateOrderFields()
                updateFields.StopPrice = self.highestSPYPrice * 0.95
                self.ticket.Update(updateFields)

    def OnOrderEvent(self, orderEvent) -> None:
        if self.ticket is not None and self.ticket.OrderId == orderEvent.OrderId:
            self.stopMarketOrderFillTime = self.Time

        # if orderEvent.Status == OrderStatus.Filled:
        #     if orderEvent.OrderId == self.ticket.OrderId:
        #         self.stop_loss = self.StopMarketOrder(orderEvent.instrument, -orderEvent.FillQuantity, orderEvent.FillPrice*0.95)
        #         self.take_profit = self.LimitOrder(orderEvent.instrument, -orderEvent.FillQuantity, orderEvent.FillPrice*1.10)

        #     elif self.stop_loss is not None and orderEvent.OrderId == self.stop_loss.OrderId:
        #         self.take_profit.Cancel()

        #     elif self.take_profit is not None and orderEvent.OrderId == self.take_profit.OrderId:
        #         self.stop_loss.Cancel()
# region imports
from AlgorithmImports import *
# endregion

class OpeningRangeBreakout(QCAlgorithm):

    quantity = 100
    stopMarketOrderFillTime = datetime.min
    highestSPYPrice = -1
    warmup = False

    ticket = None
    stop_loss = None
    take_profit = None

    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2023, 6, 1)
        self.SetCash(1000000)

        self.instrument = self.AddEquity("QQQ", Resolution.Minute)
        self.instrument.SetDataNormalizationMode(DataNormalizationMode.Raw)

        #Order at the start of the day
        self.Schedule.On(self.DateRules.EveryDay(self.instrument.Symbol), self.TimeRules.AfterMarketOpen(self.instrument.Symbol, 0), self.AtOpeningBell)

        #Close at 10:30
        self.Schedule.On(self.DateRules.EveryDay(self.instrument.Symbol), self.TimeRules.At(10, 30), self.ClosePositions)


    def ClosePositions(self):        
        if self.Portfolio.Invested:
            self.Liquidate()            
        pass

    def OnWarmupFinished(self) -> None:
        self.warmup = True # Done warming up        

    def AtOpeningBell(self) -> None:
        if self.warmup:
            self.Log("Opening Bell!")        
            self.ticket = self.StopMarketOrder(self.instrument.Symbol, self.quantity, 0.98 * self.instrument.Close)

    def OnData(self, data):
        if self.Portfolio.Invested:
            if self.instrument.Close > self.highestSPYPrice:
                self.highestSPYPrice = self.instrument.Close
                updateFields = UpdateOrderFields()
                updateFields.StopPrice = self.highestSPYPrice * 0.95
                self.ticket.Update(updateFields)

    def OnOrderEvent(self, orderEvent) -> None:
        if self.ticket is not None and self.ticket.OrderId == orderEvent.OrderId:
            self.stopMarketOrderFillTime = self.Time

        # if orderEvent.Status == OrderStatus.Filled:
        #     if orderEvent.OrderId == self.ticket.OrderId:
        #         self.stop_loss = self.StopMarketOrder(orderEvent.instrument, -orderEvent.FillQuantity, orderEvent.FillPrice*0.95)
        #         self.take_profit = self.LimitOrder(orderEvent.instrument, -orderEvent.FillQuantity, orderEvent.FillPrice*1.10)

        #     elif self.stop_loss is not None and orderEvent.OrderId == self.stop_loss.OrderId:
        #         self.take_profit.Cancel()

        #     elif self.take_profit is not None and orderEvent.OrderId == self.take_profit.OrderId:
        #         self.stop_loss.Cancel()


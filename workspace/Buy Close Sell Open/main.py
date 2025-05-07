from AlgorithmImports import *


class ScheduleBuyOnCloseSellOpen(QCAlgorithm):
    def Initialize(self):
        # set start and end date for backtest
        self.SetStartDate(2002, 8, 5)
        self.SetEndDate(2022, 8, 5)

        # initialize cash balance
        self.SetCash(1000000)
        
        # add an equity
        self.security = self.AddEquity("SPY", Resolution.Minute)
        

        # use Interactive Brokers model for fees
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage, AccountType.Margin)

        # benchmark against S&P 500
        self.SetBenchmark("SPY")

        # initialize closingOrderSent variable to track whether the market onClose order has been sent
        self.closingOrderSent = False

        # schedule a function to run every day just after the market opens
        self.Schedule.On(self.DateRules.EveryDay(self.security.Symbol), self.TimeRules.AfterMarketOpen(self.security.Symbol, 1), self.SellOpen)


    def SellOpen(self):
        # if we are invested at the open, liquidate our holdings
        if self.Portfolio.Invested:
            self.Liquidate()
            self.closingOrderSent = False


    def OnData(self, data):
        # send a market on close order if it's the last hour of the day, we are not invested, and we have not sent it yet
        if self.Time.hour == 15 and not self.Portfolio.Invested and not self.closingOrderSent:
            # calculate quantity of shares needed to use 100% of our cash
            quantity = self.CalculateOrderQuantity(self.security.Symbol, 1)
            # send the market on close order
            self.MarketOnCloseOrder(self.security.Symbol, quantity)
            # reset the closingOrderSent variable for the next day
            self.closingOrderSent = True

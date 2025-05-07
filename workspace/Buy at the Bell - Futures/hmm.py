#region imports
from collections import deque
import math
from AlgorithmImports import *
#endregion



            
class FormalFluorescentYellowArmadillo(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2019, 1, 1)  # Set Start Date
        self.SetEndDate(2019, 2, 1)  # Set End Date
        self.SetCash(1000000)  # Set Strategy Cash

        # Setting AAPL as our stock of choice and getting the corresponding symbol object
        apple = self.AddEquity("AAPL", Resolution.Minute)
        self.aapl = apple.Symbol

        # The distribution of weights to use to smooth the data
        self.weights = [0.2, 0.2, 0.2, 0.1, 0.1, 0.1, 0.05, 0.05]

        # To store the most recent $8$ prices
        self.prices_q = deque(maxlen=len(self.weights))

        self.LOWER_BOUND = self.GetParameter("lower_bound", 0.01)
        self.UPPER_BOUND = self.GetParameter("upper_bound", 2.0)
        self.LOT_SIZE = 3


    def ESmoothAvg(self, prices_q):
        avg = 0
        for i in range(len(self.weights)):
            avg += self.weights[i] * prices_q[i]
        return avg

    def ESmoothStdDev(self, prices_q):
        avg = self.ESmoothAvg(prices_q)
        squared_diff_sum = 0
        
        for i in range(len(self.weights)):
            squared_diff_sum += self.weights[i] * (prices_q[i] - avg) ** 2

        stddev = math.sqrt(squared_diff_sum)
        return stddev

    def OnData(self, data):
        if not self.aapl in data:
            return

        if not hasattr(data[self.aapl], "Open"):
            print(f"Symbol {self.aapl} does not have an 'Open' attribute")
            return

        last_open = data[self.aapl].Open
        last_close = data[self.aapl].Close
        mid_bar_price = (last_open + last_close) / 2
        self.prices_q.append(mid_bar_price)

        if len(self.prices_q) == len(self.weights):

            average = self.ESmoothAvg(self.prices_q)
            stddev = self.ESmoothStdDev(self.prices_q)

            self.Log("=====AVERAGE of " + str(average) + "=======")
            self.Log("-----CURRENT of " + str(mid_bar_price) + "-----")
            if average - (self.UPPER_BOUND * stddev) < mid_bar_price and mid_bar_price < average - (self.LOWER_BOUND * stddev):
                self.ticket = self.MarketOrder(self.aapl, self.LOT_SIZE)
                p = self.ticket.AverageFillPrice
                self.Log("BUYING 3 AAPL @ " + str(p) + '\n')
                
            elif average + (self.LOWER_BOUND * stddev) < mid_bar_price and mid_bar_price < average + (self.UPPER_BOUND * stddev):
                self.ticket = self.MarketOrder(self.aapl, -1 * self.LOT_SIZE)
                p = p = self.ticket.AverageFillPrice
                self.Log("SELLING 3 AAPL @ " + str(p) + '\n')

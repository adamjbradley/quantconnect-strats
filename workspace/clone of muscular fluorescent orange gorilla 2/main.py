# region imports
from AlgorithmImports import *
# endregion

class MuscularFluorescentOrangeGorilla(QCAlgorithm):

    def Initialize(self):

        # Set Start Date
        self.SetStartDate(2022, 6, 22)

        # Set Strategy Cash
        self.SetCash(100000)

        # Add future
        future = self.AddFuture(Futures.Energies.CrudeOilWTI, leverage = 50)
        future.SetFilter(0, 180)
        self.future_symbol = future.Symbol

    def OnData(self, data: Slice):
        
        # If not invested
        if not self.Portfolio.Invested:

            # Buy
            chain = data.FuturesChains.get(self.future_symbol)
            if chain:
                for contract in chain:
                    self.MarketOrder(contract.Symbol, (self.Portfolio.Cash * 50 / (self.Securities[contract.Symbol].Close * 1000)))
                    break

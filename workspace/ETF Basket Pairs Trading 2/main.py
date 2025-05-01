# region imports
from AlgorithmImports import *
from universe import SectorETFUniverseSelectionModel
from portfolio import CointegratedVectorPortfolioConstructionModel
# endregion

class ETFPairsTrading(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2019, 1, 1)  # Set Start Date
        self.SetCash(1000000)  # Set Strategy Cash

        lookback = self.GetParameter("lookback", 50)   # lookback window on correlation & coinetgration
        threshold = self.GetParameter("threshold", 3)   # we want at least 2+% expected profit margin to cover fees
        
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage, AccountType.Margin)
        # This should be a intra-day strategy
        self.SetSecurityInitializer(lambda security: security.SetMarginModel(PatternDayTradingMarginModel()))
        
        self.UniverseSettings.Resolution = Resolution.Minute
        self.SetUniverseSelection(SectorETFUniverseSelectionModel(self.UniverseSettings))

        # This alpha model helps to pick the most correlated pair
        # and emit signal when they have mispricing that stay active for a predicted period
        # https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/alpha/supported-models#09-Pearson-Correlation-Pairs-Trading-Model
        self.AddAlpha(PearsonCorrelationPairsTradingAlphaModel(lookback, Resolution.Daily, threshold=threshold))

        # We try to use cointegrating vector to decide the relative movement magnitude of the paired assets
        pcm = CointegratedVectorPortfolioConstructionModel(self, lookback, Resolution.Daily)
        pcm.RebalancePortfolioOnSecurityChanges = False
        self.SetPortfolioConstruction(pcm)

        self.SetWarmUp(timedelta(90))


#region imports
from AlgorithmImports import *
from Portfolio.EqualWeightingPortfolioConstructionModel import EqualWeightingPortfolioConstructionModel
from arch.unitroot.cointegration import engle_granger
#endregion

class CointegratedVectorPortfolioConstructionModel(EqualWeightingPortfolioConstructionModel):

    def __init__(self, algorithm, lookback = 252, resolution = Resolution.Minute, 
                 rebalance = Expiry.EndOfWeek) -> None:
        super().__init__(rebalance, PortfolioBias.LongShort)
        self.algorithm = algorithm
        self.lookback = lookback
        self.resolution = resolution
        self.symbol_data = {}

    def ShouldCreateTargetForInsight(self, insight: Insight) -> bool:
        # Ignore insights if the asset has open position in the same direction
        return self.symbol_data[insight.Symbol].ShouldCreateNewTarget(insight.Direction)

    def DetermineTargetPercent(self, activeInsights: List[Insight]) -> Dict[Insight, float]:
        result = {}

        # Reset indicators when corporate actions occur
        for symbol in self.algorithm.CurrentSlice.Splits.keys():
            if symbol in self.symbol_data:
                self.symbol_data[symbol].Reset()
                self.symbol_data[symbol].WarmUpIndicator()
        for symbol in self.algorithm.CurrentSlice.Dividends.keys():
            if symbol in self.symbol_data:
                self.symbol_data[symbol].Reset()
                self.symbol_data[symbol].WarmUpIndicator()

        # If less than 2 active insights, no valid pair trading can be resulted
        if len(activeInsights) < 2:
            self.LiveLog(self.algorithm, f'PortfolioContructionModel: Less then 2 insights. Create zero-quantity targets')
            return {insight: 0 for insight in activeInsights}

        # Get log return for cointegrating vector regression
        logr = pd.DataFrame({symbol: data.Return for symbol, data in self.symbol_data.items()
            if symbol in [x.Symbol for x in activeInsights]})
        # fill nans with mean, if the whole column is nan, drop it
        logr = logr.fillna(logr.mean()).dropna(axis=1)
        # make sure we have at least 2 columns
        if logr.shape[1] < 2:
            self.LiveLog(self.algorithm, f'PortfolioContructionModel: Less then 2 insights. Create zero-quantity targets.')
            return {insight: 0 for insight in activeInsights}
        # Obtain the cointegrating vector of all signaled assets for statistical arbitrage
        model = engle_granger(logr.iloc[:, 0], logr.iloc[:, 1:], trend='n', lags=0)
        
        # If result not significant, return
        if model.pvalue > 0.05:
            return {insight: 0 for insight in activeInsights}
        
        # Normalization for budget constraint
        coint_vector = model.cointegrating_vector
        total_weight = sum(abs(coint_vector))

        for insight, weight in zip(activeInsights, coint_vector):
            # we can assume any paired assets' 2 dimensions in coint_vector are in opposite sign
            result[insight] = abs(weight) / total_weight * insight.Direction
        
        return result
        
    def OnSecuritiesChanged(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        self.LiveLog(algorithm, f'PortfolioContructionModel.OnSecuritiesChanged: Changes: {changes}')
        super().OnSecuritiesChanged(algorithm, changes)
        for removed in changes.RemovedSecurities:
            symbolData = self.symbol_data.pop(removed.Symbol, None)
            if symbolData:
                symbolData.Dispose()

        for added in changes.AddedSecurities:
            symbol = added.Symbol
            if symbol not in self.symbol_data:
                symbolData = self.SymbolData(algorithm, symbol, self.lookback, self.resolution)
                self.symbol_data[symbol] = symbolData

    def LiveLog(self, algorithm, message):
        if algorithm.LiveMode:
            algorithm.Log(message)

    class SymbolData:

        def __init__(self, algorithm, symbol, lookback, resolution):
            self.algorithm = algorithm
            self.symbol = symbol
            self.lookback = lookback
            self.resolution = resolution

            # To store the historical daily log return
            self.windows = RollingWindow[IndicatorDataPoint](lookback)

            # Use daily log return to predict cointegrating vector
            self.logr = LogReturn(1)
            self.logr.Updated += self.OnUpdate
            self.consolidator = TradeBarConsolidator(timedelta(1))

            # Subscribe the consolidator and indicator to data for automatic update
            algorithm.RegisterIndicator(symbol, self.logr, self.consolidator)
            algorithm.SubscriptionManager.AddConsolidator(symbol, self.consolidator)

            self.WarmUpIndicator()

        def WarmUpIndicator(self):
            # historical warm-up on the log return indicator
            history = self.algorithm.History[TradeBar](self.symbol, self.lookback, self.resolution)
            for bar in list(history)[:-1]:
                self.logr.Update(bar.EndTime, bar.Close)

        def OnUpdate(self, sender, updated):
            self.windows.Add(IndicatorDataPoint(updated.EndTime, updated.Value))

        def Dispose(self):
            self.logr.Updated -= self.OnUpdate
            self.Reset()
            self.algorithm.SubscriptionManager.RemoveConsolidator(self.symbol, self.consolidator)
        
        def Reset(self):
            self.logr.Reset()
            self.windows.Reset()

        def ShouldCreateNewTarget(self, direction):
            quantity = self.algorithm.Portfolio[self.symbol].Quantity
            return quantity == 0 or direction != np.sign(quantity)

        @property
        def Return(self):
            return pd.Series(
                data = [x.Value for x in self.windows],
                index = [x.EndTime.date() for x in self.windows])[::-1]


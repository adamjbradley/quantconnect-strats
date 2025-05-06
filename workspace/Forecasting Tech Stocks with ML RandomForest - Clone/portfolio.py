# We re-define the MeanVarianceOptimizationPortfolioConstructionModel because
# - The model doesn't warm-up with ScaledRaw data (https://github.com/QuantConnect/Lean/issues/7239)
# - The original definition doesn't reset the `roc` and `window` in the `MeanVarianceSymbolData` objects when corporate actions occur

from AlgorithmImports import *

from Portfolio.MinimumVariancePortfolioOptimizer import MinimumVariancePortfolioOptimizer


### <summary>
### Provides an implementation of Mean-Variance portfolio optimization based on modern portfolio theory.
### The default model uses the MinimumVariancePortfolioOptimizer that accepts a 63-row matrix of 1-day returns.
### </summary>
class MeanVarianceOptimizationPortfolioConstructionModel(PortfolioConstructionModel):
    def __init__(self,
                 algorithm,
                 rebalance = Resolution.DAILY,
                 portfolio_bias = PortfolioBias.LONG_SHORT,
                 lookback = 1,
                 period = 63,
                 resolution = Resolution.DAILY,
                 target_return = 0.02,
                 optimizer = None):
        """Initialize the model
        Args:
            rebalance: Rebalancing parameter. If it is a timedelta, date rules or Resolution, it will be converted into a function.
                              If None will be ignored.
                              The function returns the next expected rebalance time for a given algorithm UTC DateTime.
                              The function returns null if unknown, in which case the function will be called again in the
                              next loop. Returning current time will trigger rebalance.
            portfolio_bias: Specifies the bias of the portfolio (Short, Long/Short, Long)
            lookback(int): Historical return lookback period
            period(int): The time interval of history price to calculate the weight
            resolution: The resolution of the history price
            optimizer(class): Method used to compute the portfolio weights"""
        super().__init__()
        self._algorithm = algorithm
        self._lookback = lookback
        self._period = period
        self._resolution = resolution
        self._portfolio_bias = portfolio_bias
        self._sign = lambda x: -1 if x < 0 else (1 if x > 0 else 0)

        lower = algorithm.settings.min_absolute_portfolio_target_percentage*1.1 if portfolio_bias == PortfolioBias.LONG else -1
        upper = 0 if portfolio_bias == PortfolioBias.SHORT else 1
        self._optimizer = MinimumVariancePortfolioOptimizer(lower, upper, target_return) if optimizer is None else optimizer

        self._symbol_data_by_symbol = {}
        self._new_insights = False

    def is_rebalance_due(self, insights, algorithmUtc):
        if not self._new_insights:
            self._new_insights = len(insights) > 0
        is_rebalance_due = self._new_insights and not self._algorithm.is_warming_up and self._algorithm.current_slice.quote_bars.count > 0
        if is_rebalance_due:
            self._new_insights = False
        return is_rebalance_due

    def create_targets(self, algorithm, insights):
        # Reset and warm-up indicators when corporate actions occur
        data = algorithm.current_slice
        reset_symbols = []
        for symbol in set(data.dividends.keys()) | set(data.splits.keys()):
            symbol_data = self._symbol_data_by_symbol[symbol]
            if symbol_data.should_reset():
                symbol_data.clear_history()
                reset_symbols.append(symbol)
        if reset_symbols:
            self._warm_up(algorithm, reset_symbols)

        return super().create_targets(algorithm, insights)

    def should_create_target_for_insight(self, insight):
        if len(PortfolioConstructionModel.filter_invalid_insight_magnitude(self._algorithm, [insight])) == 0:
            return False

        symbol_data = self._symbol_data_by_symbol.get(insight.symbol)
        if insight.magnitude is None:
            self._algorithm.set_run_time_error(ArgumentNullException('MeanVarianceOptimizationPortfolioConstructionModel does not accept \'None\' as Insight.magnitude. Please checkout the selected Alpha Model specifications.'))
            return False
        symbol_data.add(self._algorithm.time, insight.magnitude)

        return True

    def determine_target_percent(self, activeInsights):
        """
         Will determine the target percent for each insight
        Args:
        Returns:
        """
        targets = {}

        # If we have no insights just return an empty target list
        if len(activeInsights) == 0:
            return targets

        symbols = [insight.symbol for insight in activeInsights]

        # Create a dictionary keyed by the symbols in the insights with an pandas.series as value to create a data frame
        returns = { str(symbol.id) : data.return_ for symbol, data in self._symbol_data_by_symbol.items() if symbol in symbols }
        returns = pd.DataFrame(returns)

        # The portfolio optimizer finds the optional weights for the given data
        weights = self._optimizer.optimize(returns)
        weights = pd.Series(weights, index = returns.columns)

        # Create portfolio targets from the specified insights
        for insight in activeInsights:
            weight = weights[str(insight.symbol.id)]

            # don't trust the optimizer
            if self._portfolio_bias != PortfolioBias.LONG_SHORT and self._sign(weight) != self._portfolio_bias:
                weight = 0
            targets[insight] = weight

        return targets

    def on_securities_changed(self, algorithm, changes):
        # clean up data for removed securities
        super().on_securities_changed(algorithm, changes)
        for removed in changes.removed_securities:
            symbol_data = self._symbol_data_by_symbol.pop(removed.symbol, None)
            symbol_data.reset()

        # initialize data for added securities
        symbols = [x.symbol for x in changes.added_securities]
        for symbol in [x for x in symbols if x not in self._symbol_data_by_symbol]:
            self._symbol_data_by_symbol[symbol] = self.MeanVarianceSymbolData(symbol, self._lookback, self._period)
        self._warm_up(algorithm, symbols)
    
    def _warm_up(self, algorithm, symbols):
        history = algorithm.history[TradeBar](symbols, self._lookback * self._period + 1, self._resolution, data_normalization_mode=DataNormalizationMode.SCALED_RAW)
        for bars in history:
            for symbol, bar in bars.items():
                self._symbol_data_by_symbol.get(symbol).update(bar.end_time, bar.value)


    class MeanVarianceSymbolData:
        def __init__(self, symbol, lookback, period):
            self._symbol = symbol
            self._roc = RateOfChange(f'{symbol}.ROC({lookback})', lookback)
            self._roc.updated += self._on_rate_of_change_updated
            self._window = RollingWindow[IndicatorDataPoint](period)

        def should_reset(self):
            # Don't need to reset when the `window` only contain data from the insight.magnitude
            return self._window.samples < self._window.size * 2
        
        def clear_history(self):
            self._roc.reset()
            self._window.reset()

        def reset(self):
            self._roc.updated -= self._on_rate_of_change_updated
            self.clear_history()

        def update(self, time, value):
            return self._roc.update(time, value)

        def _on_rate_of_change_updated(self, roc, value):
            if roc.is_ready:
                self._window.add(value)

        def add(self, time, value):
            item = IndicatorDataPoint(self._symbol, time, value)
            self._window.add(item)

        # Get symbols' returns, we use simple return according to
        # Meucci, Attilio, Quant Nugget 2: Linear vs. Compounded Returns – Common Pitfalls in Portfolio Management (May 1, 2010). 
        # GARP Risk Professional, pp. 49-51, April 2010 , Available at SSRN: https://ssrn.com/abstract=1586656
        @property
        def return_(self):
            return pd.Series(
                data = [x.value for x in self._window],
                index = [x.end_time for x in self._window])

        @property
        def is_ready(self):
            return self._window.is_ready


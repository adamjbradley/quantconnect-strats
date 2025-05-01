#region imports
from AlgorithmImports import *

from sklearn.ensemble import RandomForestRegressor
#endregion


class RandomForestAlphaModel(AlphaModel):

    _securities = []
    _scheduled_event = None
    _time = datetime.min
    _rebalance = False

    def __init__(self, algorithm, minutes_before_close, n_estimators, min_samples_split, lookback_days):
        self._algorithm = algorithm
        self._minutes_before_close = minutes_before_close
        self._n_estimators = n_estimators
        self._min_samples_split = min_samples_split
        self._lookback_days = lookback_days

    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        if not self._rebalance or data.quote_bars.count == 0:
            return []
        
        # Fetch history on our universe
        symbols = [s.symbol for s in self._securities]
        df = algorithm.history(symbols, 2, Resolution.DAILY, data_normalization_mode=DataNormalizationMode.SCALED_RAW)
        if df.empty: 
            return []

        self._rebalance = False
    
        # Make all of them into a single time index.
        df = df.close.unstack(level=0)
    
        # Feature engineer the data for input
        input_ = df.diff() * 0.5 + df * 0.5
        input_ = input_.iloc[-1].fillna(0).values.reshape(1, -1)
        
        # Predict the expected price
        predictions = self._regressor.predict(input_)
        
        # Get the expected return
        predictions = (predictions - df.iloc[-1].values) / df.iloc[-1].values
        predictions = predictions.flatten()
        
        insights = []
        for i in range(len(predictions)):
            insights.append( Insight.price(df.columns[i], timedelta(5), InsightDirection.UP, predictions[i]) )
        algorithm.insights.cancel(symbols)
        return insights

    def _train_model(self):
        # Initialize the Random Forest Regressor
        self._regressor = RandomForestRegressor(n_estimators=self._n_estimators, min_samples_split=self._min_samples_split, random_state = 1990)
        
        # Get historical data
        history = self._algorithm.history([s.symbol for s in self._securities], self._lookback_days, Resolution.DAILY, data_normalization_mode=DataNormalizationMode.SCALED_RAW)
        
        # Select the close column and then call the unstack method.
        df = history['close'].unstack(level=0)
        
        # Feature engineer the data for input.
        input_ = df.diff() * 0.5 + df * 0.5
        input_ = input_.iloc[1:].ffill().fillna(0)
        
        # Shift the data for 1-step backward as training output result.
        output = df.shift(-1).iloc[:-1].ffill().fillna(0)
        
        # Fit the regressor
        self._regressor.fit(input_, output)


    def _before_market_close(self):
        if self._time < self._algorithm.time:
            self._train_model()
            self._time = Expiry.end_of_month(self._algorithm.time)
        self._rebalance = True

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        for security in changes.removed_securities:
            if security in self._securities:
                self._securities.remove(security)
                
        for security in changes.added_securities:
            self._securities.append(security)

            # Add Scheduled Event
            if self._scheduled_event == None:
                symbol = security.symbol
                self._scheduled_event = algorithm.schedule.on(
                    algorithm.date_rules.every_day(symbol), 
                    algorithm.time_rules.before_market_close(symbol, self._minutes_before_close), 
                    self._before_market_close
                )


# region imports
from AlgorithmImports import *

from alpha import RandomForestAlphaModel
from portfolio import MeanVarianceOptimizationPortfolioConstructionModel
# endregion


class RandomForestAlgorithm(QCAlgorithm):

    _undesired_symbols_from_previous_deployment = []
    _checked_symbols_from_previous_deployment = False

    def initialize(self):
        self.set_start_date(2022, 6, 1)
        self.set_end_date(2023, 6, 1)
        self.set_cash(1_000_000)
        
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.settings.minimum_order_margin_portfolio_percentage = 0

        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW
        tickers = ["SHY", "TLT", "IEI", "SHV", "TLH", "EDV", "BIL", "SPTL", "TBT", "TMF", 
                    "TMV", "TBF", "VGSH", "VGIT", "VGLT", "SCHO", "SCHR", "SPTS", "GOVT"]
        symbols = [ Symbol.create(ticker, SecurityType.EQUITY, Market.USA) for ticker in tickers]
        self.add_universe_selection(ManualUniverseSelectionModel(symbols))

        self.add_alpha(RandomForestAlphaModel(
            self,
            self.get_parameter("minutes_before_close", 5),
            self.get_parameter("n_estimators", 100),
            self.get_parameter("min_samples_split", 5),
            self.get_parameter("lookback_days", 360)
        ))

        self.set_portfolio_construction(MeanVarianceOptimizationPortfolioConstructionModel(self, lambda time: None, PortfolioBias.LONG, period=self.get_parameter("pcm_periods", 5)))
        
        self.add_risk_management(NullRiskManagementModel())

        self.set_execution(ImmediateExecutionModel())

        self.set_warm_up(timedelta(5))

    def on_data(self, data):
        # Exit positions that aren't backed by existing insights.
        # If you don't want this behavior, delete this method definition.
        if not self.is_warming_up and not self._checked_symbols_from_previous_deployment:
            for security_holding in self.portfolio.values():
                if not security_holding.invested:
                    continue
                symbol = security_holding.symbol
                if not self.insights.has_active_insights(symbol, self.utc_time):
                    self._undesired_symbols_from_previous_deployment.append(symbol)
            self._checked_symbols_from_previous_deployment = True
        
        for symbol in self._undesired_symbols_from_previous_deployment[:]:
            if self.is_market_open(symbol):
                self.liquidate(symbol, tag="Holding from previous deployment that's no longer desired")
                self._undesired_symbols_from_previous_deployment.remove(symbol)

